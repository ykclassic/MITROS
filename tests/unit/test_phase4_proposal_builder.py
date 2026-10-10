from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from contracts.domain import Direction, StrategyVote
from contracts.phase4_risk import RiskDisposition, RiskEvaluationRequest, RiskPolicy
from contracts.signal import SignalRecord
from packages.proposals.phase4_builder import Phase4TradeProposalBuilder
from packages.risk.phase4 import IndependentRiskGate


def policy() -> RiskPolicy:
    return RiskPolicy(
        max_risk_per_trade=Decimal("0.01"), max_position_fraction=Decimal("0.20"),
        max_gross_exposure_fraction=Decimal("1.0"), max_daily_loss_fraction=Decimal("0.03"),
        max_drawdown_fraction=Decimal("0.10"), max_asset_concentration_fraction=Decimal("0.30"),
        max_correlated_positions=2, max_correlated_exposure_fraction=Decimal("0.40"),
        max_open_positions=5, min_risk_reward=Decimal("2"),
        max_spread_fraction=Decimal("0.002"), max_slippage_fraction=Decimal("0.001"),
        min_data_quality=Decimal("0.90"), max_quote_age_seconds=60,
        max_account_age_seconds=120,
    )


def signal(now: datetime) -> SignalRecord:
    return SignalRecord(
        id=uuid4(), asset="BTC/USD", venue="spot", direction=Direction.LONG,
        created_at=now, expires_at=now + timedelta(minutes=15),
        strategy_votes=(StrategyVote(
            strategy_id="smc", strategy_version="1.0.0",
            direction=Direction.LONG, confidence=Decimal("0.9"),
        ),),
        confidence=Decimal("0.9"),
    )


def request(proposal_id: str, **overrides: object) -> RiskEvaluationRequest:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "proposal_id": proposal_id, "asset": "BTC/USD", "correlated_group": "BTC-beta",
        "direction": Direction.LONG, "as_of": now, "quote_observed_at": now - timedelta(seconds=5),
        "verified_reference_price": Decimal("100"), "current_market_price": Decimal("100"),
        "data_verified": True, "data_quality": Decimal("0.99"), "equity": Decimal("10000"),
        "daily_pnl": Decimal("0"), "peak_equity": Decimal("10000"), "open_positions": (),
        "account_snapshot_at": now - timedelta(seconds=5),
        "requested_notional": Decimal("1000"), "entry": Decimal("100"), "stop_loss": Decimal("95"),
        "take_profit": Decimal("110"), "spread_fraction": Decimal("0.001"),
        "expected_slippage_fraction": Decimal("0.0005"),
    }
    values.update(overrides)
    return RiskEvaluationRequest.model_validate(values)


def test_phase4_builder_requires_passing_independent_decision() -> None:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    candidate = signal(now)
    inputs = request(str(candidate.id))
    decision = IndependentRiskGate(policy()).evaluate(inputs)
    proposal = Phase4TradeProposalBuilder().build(
        candidate, inputs, decision, venue="spot", regime="TREND_UP",
        mtf_alignment=Decimal("0.9"), now=now,
    )
    assert proposal.id == candidate.id
    assert proposal.position_size == decision.approved_notional
    assert proposal.invalidation_conditions == decision.invalidation_conditions
    assert proposal.execution_status.value == "NOT_AUTHORIZED"


def test_phase4_builder_cannot_bypass_rejected_risk_check() -> None:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    candidate = signal(now)
    inputs = request(str(candidate.id), data_verified=False)
    decision = IndependentRiskGate(policy()).evaluate(inputs)
    assert decision.disposition is RiskDisposition.REJECTED
    with pytest.raises(ValueError, match="risk decision rejected"):
        Phase4TradeProposalBuilder().build(
            candidate, inputs, decision, venue="spot", regime="TREND_UP",
            mtf_alignment=Decimal("0.9"), now=now,
        )


def test_phase4_builder_rejects_mismatched_signal_identity() -> None:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    candidate = signal(now)
    inputs = request("not-the-signal-id")
    decision = IndependentRiskGate(policy()).evaluate(inputs)
    with pytest.raises(ValueError, match="identifiers must match"):
        Phase4TradeProposalBuilder().build(
            candidate, inputs, decision, venue="spot", regime="TREND_UP",
            mtf_alignment=Decimal("0.9"), now=now,
        )
