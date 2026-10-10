from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg
from loguru import logger
from psycopg.rows import dict_row

from packages.exchanges.xt import XTSpotClient, XTSpotError
from packages.execution.interface import ExecutionResult
from packages.execution.xt import XTExecutionError, XTSpotExecutionGateway
from packages.operations.config import ExecutionMode, ProductionConfig


def protection_trigger_reason(
    *, direction: str, price: Decimal, stop_loss: Decimal, take_profit: Decimal
) -> str | None:
    """Return the protective exit reason when a verified current price crosses a level."""
    if direction.upper() == "LONG":
        if price <= stop_loss:
            return "STOP_LOSS_TRIGGERED"
        if price >= take_profit:
            return "TAKE_PROFIT_TRIGGERED"
        return None
    if direction.upper() == "SHORT":
        if price >= stop_loss:
            return "STOP_LOSS_TRIGGERED"
        if price <= take_profit:
            return "TAKE_PROFIT_TRIGGERED"
    return None


class XTSpotProtectionMonitor:
    """Polls filled XT spot entries and submits one idempotent risk-reducing close when triggered."""

    def __init__(
        self,
        database_url: str,
        *,
        xt: XTSpotClient | None = None,
        gateway: XTSpotExecutionGateway | None = None,
    ) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url
        self.xt = xt or XTSpotClient()
        self.gateway = gateway or XTSpotExecutionGateway()

    def enabled(self) -> bool:
        try:
            config = ProductionConfig.from_env()
        except ValueError:
            return False
        return (
            config.execution_mode is ExecutionMode.LIVE
            and config.live_trading_enabled
            and config.live_trading_acknowledged
            and os.getenv("MITROS_XT_LIVE_ORDERS_ENABLED", "false").strip().lower() == "true"
            and os.getenv("MITROS_XT_PROTECTION_MONITOR_ENABLED", "false").strip().lower() == "true"
        )

    async def run_once(self) -> int:
        if not self.enabled():
            return 0
        await self._reconcile_entries()
        await self._activate_filled_entries()
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                select proposal_id, owner_user_id, asset, direction, entry_quantity,
                       stop_loss, take_profit, status, exit_client_order_id
                from phase4_protective_positions
                where status in ('ACTIVE', 'EXITING')
                order by created_at asc
                """
            )
            rows = await cursor.fetchall()

        actions = 0
        max_age = int(os.getenv("MITROS_RISK_MAX_QUOTE_AGE_SECONDS", "60"))
        now = datetime.now(UTC)
        for row in rows:
            proposal_id = str(row["proposal_id"])
            if row["status"] == "EXITING":
                await self._reconcile_exit(row)
                continue
            try:
                ticker = await self.xt.market_ticker(str(row["asset"]))
                observed_at = ticker["observed_at"]
                if not isinstance(observed_at, datetime):
                    continue
                age = (now - observed_at).total_seconds()
                if age < 0 or age > max_age:
                    logger.warning("xt_protection_quote_stale proposal_id=%s age_seconds=%s", proposal_id, age)
                    continue
                price = Decimal(str(ticker["last"]))
                reason = protection_trigger_reason(
                    direction=str(row["direction"]),
                    price=price,
                    stop_loss=Decimal(str(row["stop_loss"])),
                    take_profit=Decimal(str(row["take_profit"])),
                )
                await self._record_mark(proposal_id, price, observed_at)
                if reason is None:
                    continue
                client_order_id = f"exit-{proposal_id}"
                claimed = await self._claim_exit(proposal_id, client_order_id, reason, price)
                if not claimed:
                    continue
                result = self.gateway.submit_protective_close(
                    asset=str(row["asset"]),
                    quantity=Decimal(str(row["entry_quantity"])),
                    client_order_id=client_order_id,
                )
                await self._record_exit_result(proposal_id, result)
                actions += 1
            except (XTSpotError, XTExecutionError, psycopg.Error, ValueError) as exc:
                logger.error(
                    "xt_protection_monitor_error proposal_id=%s category=%s",
                    proposal_id, type(exc).__name__,
                )
                # Once EXITING is claimed, never submit a second close blindly.
                continue
        return actions

    async def _reconcile_entries(self) -> None:
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                select o.client_order_id, o.trade_proposal_id, p.owner_user_id
                from orders o join trade_proposals p on p.id=o.trade_proposal_id
                where o.venue='xt.com' and o.status in ('SUBMITTED', 'PARTIALLY_FILLED')
                  and p.owner_user_id is not null
                """
            )
            rows = await cursor.fetchall()
        from packages.proposals.persistence import PostgresPhase4ProposalRepository

        for row in rows:
            try:
                result = self.gateway.reconcile(str(row["client_order_id"]))
                if result is None:
                    continue
                await PostgresPhase4ProposalRepository(self.database_url).record_execution(
                    user_id=str(row["owner_user_id"]),
                    proposal_id=row["trade_proposal_id"],
                    result=result,
                )
            except (XTExecutionError, psycopg.Error, ValueError) as exc:
                logger.warning("xt_entry_reconciliation_error category=%s", type(exc).__name__)

    async def _activate_filled_entries(self) -> None:
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.transaction(), connection.cursor() as cursor:
            await cursor.execute(
                """
                select o.trade_proposal_id, o.venue_order_id, o.payload as order_payload,
                       p.owner_user_id, p.payload as proposal_payload
                from orders o join trade_proposals p on p.id=o.trade_proposal_id
                left join phase4_protective_positions protection on protection.proposal_id=o.trade_proposal_id
                where o.venue='xt.com'
                  and o.status in ('FILLED', 'PARTIALLY_FILLED', 'CANCELLED')
                  and coalesce((o.payload->>'filled_quantity')::numeric, 0) > 0
                  and p.direction='LONG'
                  and protection.proposal_id is null
                """
            )
            rows = await cursor.fetchall()
            for row in rows:
                order_payload = row["order_payload"]
                proposal_payload = row["proposal_payload"]
                await cursor.execute(
                    """
                    insert into phase4_protective_positions (
                        proposal_id, owner_user_id, asset, direction, entry_quantity,
                        stop_loss, take_profit, status, entry_order_id
                    ) values (%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s)
                    on conflict (proposal_id) do nothing
                    """,
                    (
                        row["trade_proposal_id"], row["owner_user_id"],
                        proposal_payload["asset"], proposal_payload["direction"],
                        Decimal(str(order_payload["filled_quantity"])),
                        proposal_payload["stop"], proposal_payload["target"],
                        row["venue_order_id"],
                    ),
                )

    async def _record_mark(self, proposal_id: str, price: Decimal, observed_at: datetime) -> None:
        async with await psycopg.AsyncConnection.connect(self.database_url) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                update phase4_protective_positions
                set last_price=%s, last_checked_at=%s, updated_at=now()
                where proposal_id=%s and status='ACTIVE'
                """,
                (price, observed_at, proposal_id),
            )

    async def _claim_exit(
        self, proposal_id: str, client_order_id: str, reason: str, price: Decimal
    ) -> bool:
        async with await psycopg.AsyncConnection.connect(self.database_url) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                update phase4_protective_positions
                set status='EXITING', exit_client_order_id=%s, triggered_reason=%s,
                    last_price=%s, last_checked_at=now(), updated_at=now()
                where proposal_id=%s and status='ACTIVE'
                """,
                (client_order_id, reason, price, proposal_id),
            )
            return cursor.rowcount == 1

    async def _reconcile_exit(self, row: dict[str, Any]) -> None:
        client_order_id = row.get("exit_client_order_id")
        if not client_order_id:
            return
        try:
            result = self.gateway.reconcile(str(client_order_id))
        except (XTExecutionError, ValueError) as exc:
            logger.warning("xt_exit_reconciliation_error category=%s", type(exc).__name__)
            return
        if result is not None:
            await self._record_exit_result(str(row["proposal_id"]), result)

    async def _record_exit_result(self, proposal_id: str, result: ExecutionResult) -> None:
        status = "CLOSED" if result.status == "FILLED" else (
            "FAILED" if result.status in {"REJECTED", "CANCELLED"} else "EXITING"
        )
        async with await psycopg.AsyncConnection.connect(self.database_url) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                update phase4_protective_positions
                set status=%s, exit_order_id=%s, exit_status=%s, exit_filled_quantity=%s,
                    updated_at=now()
                where proposal_id=%s and status='EXITING'
                """,
                (
                    status, result.venue_order_id, result.status, result.filled_quantity,
                    proposal_id,
                ),
            )
