from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from contracts.domain import Direction
from contracts.phase4_risk import RiskDisposition, RiskEvaluationRequest, RiskPolicy
from packages.exchanges.models import AccountBalance, AccountSnapshot
from packages.risk.account_state import PostgresAccountPortfolioRepository
from packages.risk.persistence import PostgresPhase4RiskDecisionRepository
from packages.risk.phase4 import IndependentRiskGate


@pytest.fixture(scope="session", autouse=True)
def isolated_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    assert database_url, "DATABASE_URL must point to the isolated PostgreSQL service."
    parsed = urlparse(database_url)
    assert parsed.hostname in {"localhost", "127.0.0.1", "::1", "postgres"}, (
        "Integration tests may only use a local/container PostgreSQL host."
    )
    assert "mitros_test" in (parsed.path or "").lower(), (
        "Integration tests require a database name containing 'mitros_test'."
    )
    assert "production" not in database_url.lower(), (
        "Production database URLs are forbidden in integration tests."
    )
    return database_url


def _risk_policy() -> RiskPolicy:
    return RiskPolicy(
        max_risk_per_trade=Decimal("0.01"),
        max_position_fraction=Decimal("0.20"),
        max_gross_exposure_fraction=Decimal("1.0"),
        max_daily_loss_fraction=Decimal("0.03"),
        max_drawdown_fraction=Decimal("0.10"),
        max_asset_concentration_fraction=Decimal("0.30"),
        max_correlated_positions=2,
        max_correlated_exposure_fraction=Decimal("0.40"),
        max_open_positions=5,
        min_risk_reward=Decimal("2"),
        max_spread_fraction=Decimal("0.002"),
        max_slippage_fraction=Decimal("0.001"),
        min_data_quality=Decimal("0.90"),
        max_quote_age_seconds=60,
        max_account_age_seconds=120,
    )


def _risk_request(*, proposal_id: str, data_verified: bool = True) -> RiskEvaluationRequest:
    now = datetime.now(UTC)
    return RiskEvaluationRequest(
        proposal_id=proposal_id,
        asset="BTC/USDT",
        correlated_group="BTC-beta",
        direction=Direction.LONG,
        as_of=now,
        quote_observed_at=now - timedelta(seconds=1),
        verified_reference_price=Decimal("65000"),
        current_market_price=Decimal("65000"),
        account_source="bybit",
        account_snapshot_id="isolated-test-snapshot",
        account_snapshot_at=now - timedelta(seconds=1),
        market_evidence=("integration-test",),
        data_verified=data_verified,
        data_quality=Decimal("0.99"),
        equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        peak_equity=Decimal("10000"),
        open_positions=(),
        requested_notional=Decimal("100"),
        entry=Decimal("65000"),
        stop_loss=Decimal("64000"),
        take_profit=Decimal("67000"),
        spread_fraction=Decimal("0.0001"),
        expected_slippage_fraction=Decimal("0.0001"),
    )


@pytest.mark.asyncio
async def test_account_snapshot_is_persisted_and_read_back(
    isolated_database_url: str,
) -> None:
    user_id = f"integration-{uuid4()}"
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    account = AccountSnapshot(
        observed_at_ms=now_ms,
        total_btc_value=Decimal("0.2"),
        balances=(
            AccountBalance(
                currency="BTC",
                available=Decimal("0.1"),
                frozen=Decimal("0"),
                total=Decimal("0.1"),
                btc_value=Decimal("0.1"),
            ),
            AccountBalance(
                currency="USDT",
                available=Decimal("6500"),
                frozen=Decimal("0"),
                total=Decimal("6500"),
                btc_value=Decimal("0.1"),
            ),
        ),
        provider="bybit",
        account_type="unified",
    )

    repository = PostgresAccountPortfolioRepository(isolated_database_url)
    recorded = await repository.record_snapshot(
        user_id=user_id,
        account=account,
        btc_usdt_price=Decimal("65000"),
    )

    assert recorded["snapshot_id"]
    assert recorded["source"] == "bybit:unified/balances"
    assert recorded["equity"] == Decimal("13000")

    async with await psycopg.AsyncConnection.connect(
        isolated_database_url, row_factory=dict_row
    ) as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
            select id::text, user_id, venue, account_type, equity, balances, positions
            from phase4_portfolio_snapshots
            where id = %s
            """,
            (recorded["snapshot_id"],),
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row["user_id"] == user_id
    assert row["venue"] == "bybit"
    assert row["account_type"] == "unified"
    assert Decimal(str(row["equity"])) == Decimal("13000")
    assert len(row["balances"]) == 2


@pytest.mark.asyncio
async def test_risk_audit_persists_rejection_without_creating_trade_proposal(
    isolated_database_url: str,
) -> None:
    user_id = f"integration-{uuid4()}"
    request = _risk_request(proposal_id=str(uuid4()), data_verified=False)
    policy = _risk_policy()
    decision = IndependentRiskGate(policy).evaluate(request)
    assert decision.disposition is RiskDisposition.REJECTED
    assert decision.execution_authorized is False

    repository = PostgresPhase4RiskDecisionRepository(isolated_database_url)
    audit = await repository.record(
        user_id=user_id,
        idempotency_key=f"rejected-{uuid4()}",
        request=request,
        policy=policy,
        decision=decision,
        correlation_id=uuid4(),
    )

    async with await psycopg.AsyncConnection.connect(
        isolated_database_url, row_factory=dict_row
    ) as connection, connection.cursor() as cursor:
        await cursor.execute(
            """
            select disposition, decision_snapshot
            from phase4_risk_decisions
            where id = %s
            """,
            (audit["id"],),
        )
        persisted_audit = await cursor.fetchone()
        await cursor.execute(
            "select count(*) as count from trade_proposals where id::text = %s",
            (request.proposal_id,),
        )
        proposal_count = (await cursor.fetchone())["count"]

    assert persisted_audit is not None
    assert persisted_audit["disposition"] == "REJECTED"
    assert persisted_audit["decision_snapshot"]["execution_authorized"] is False
    assert proposal_count == 0
