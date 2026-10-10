from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from contracts.domain import Direction
from contracts.phase4_risk import OpenPosition
from packages.exchanges.xt import XTSpotAccount


class PortfolioSnapshotError(RuntimeError):
    """Raised when authoritative portfolio state cannot be persisted/reconstructed."""


class PostgresXTPortfolioRepository:
    """Stores XT spot snapshots and derives intraday P&L and observed equity high-water mark."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url

    async def record_snapshot(
        self,
        *,
        user_id: str,
        account: XTSpotAccount,
        btc_usdt_price: Decimal,
    ) -> dict[str, Any]:
        if not user_id or btc_usdt_price <= 0:
            raise ValueError("user_id and a positive BTC/USDT price are required")
        observed_at = datetime.fromtimestamp(account.observed_at_ms / 1000, tz=UTC)
        equity = account.total_btc_value * btc_usdt_price
        if equity <= 0:
            raise PortfolioSnapshotError("XT portfolio equity is not positive")
        positions = [
            {
                "asset": f"{item.currency}/USDT",
                "currency": item.currency,
                "notional": str(item.btc_value * btc_usdt_price),
                "correlated_group": _correlated_group(item.currency),
                "direction": "LONG",
                "available": str(item.available),
                "frozen": str(item.frozen),
                "total": str(item.total),
            }
            for item in account.balances
            if item.btc_value > 0 and item.currency not in {"USDT", "USDC", "USD"}
        ]
        balances_json = [
            {
                "currency": item.currency,
                "available": str(item.available),
                "frozen": str(item.frozen),
                "total": str(item.total),
                "btc_value": str(item.btc_value),
            }
            for item in account.balances
        ]
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict_row
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    select equity
                    from phase4_portfolio_snapshots
                    where user_id = %s and snapshot_at >= date_trunc('day', %s::timestamptz)
                    order by snapshot_at asc limit 1
                    """,
                    (user_id, observed_at),
                )
                first_today = await cursor.fetchone()
                daily_baseline = Decimal(str(first_today["equity"])) if first_today else equity
                await cursor.execute(
                    "select max(peak_equity) as peak_equity from phase4_portfolio_snapshots where user_id = %s",
                    (user_id,),
                )
                high_water = await cursor.fetchone()
                prior_peak = Decimal(str(high_water["peak_equity"])) if high_water and high_water["peak_equity"] is not None else equity
                peak_equity = max(prior_peak, equity)
                daily_pnl = equity - daily_baseline
                await cursor.execute(
                    """
                    insert into phase4_portfolio_snapshots (
                        user_id, venue, account_type, snapshot_at, equity,
                        daily_pnl, peak_equity, btc_usdt_price, balances, positions
                    ) values (%s, 'xt.com', 'spot', %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    returning id, snapshot_at
                    """,
                    (
                        user_id, observed_at, equity, daily_pnl, peak_equity,
                        btc_usdt_price, json.dumps(balances_json), json.dumps(positions),
                    ),
                )
                row = await cursor.fetchone()
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise PortfolioSnapshotError("XT portfolio snapshot persistence failed") from exc
        if row is None:
            raise PortfolioSnapshotError("XT portfolio snapshot could not be retrieved")
        open_positions = tuple(
            OpenPosition(
                asset=str(item["asset"]),
                notional=Decimal(str(item["notional"])),
                correlated_group=str(item["correlated_group"]),
                direction=Direction.LONG,
            )
            for item in positions
        )
        return {
            "snapshot_id": str(row["id"]),
            "snapshot_at": row["snapshot_at"],
            "equity": equity,
            "balance": equity,
            "daily_pnl": daily_pnl,
            "peak_equity": peak_equity,
            "open_positions": open_positions,
            "positions": positions,
            "balances": balances_json,
            "source": "xt.com:spot/v4/balances",
            "valuation_source": "xt.com:BTC/USDT",
        }


def _correlated_group(currency: str) -> str:
    groups = {
        "BTC": "BTC-beta", "ETH": "ETH-beta", "SOL": "SOL-beta",
        "BNB": "BNB-beta", "XRP": "XRP-beta", "ADA": "ADA-beta",
        "DOGE": "DOGE-beta", "LINK": "LINK-beta", "LTC": "LTC-beta",
    }
    return groups.get(currency.upper(), f"{currency.upper()}-spot")
