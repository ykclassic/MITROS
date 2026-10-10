from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest
from contracts.domain import Direction
from contracts.phase4_risk import OpenPosition, RiskDisposition, RiskEvaluationRequest, RiskPolicy
from packages.risk.phase4 import ENGINE_VERSION, IndependentRiskGate

def policy(**overrides: object) -> RiskPolicy:
    values: dict[str, object] = {
        "max_risk_per_trade": Decimal("0.01"), "max_position_fraction": Decimal("0.20"),
        "max_gross_exposure_fraction": Decimal("1.0"), "max_daily_loss_fraction": Decimal("0.03"),
        "max_drawdown_fraction": Decimal("0.10"), "max_asset_concentration_fraction": Decimal("0.30"),
        "max_correlated_positions": 2, "max_correlated_exposure_fraction": Decimal("0.40"),
        "max_open_positions": 5, "min_risk_reward": Decimal("2"),
        "max_spread_fraction": Decimal("0.002"), "max_slippage_fraction": Decimal("0.001"),
        "min_data_quality": Decimal("0.90"), "max_quote_age_seconds": 60,
    }
    values.update(overrides)
    return RiskPolicy.model_validate(values)

def request(**overrides: object) -> RiskEvaluationRequest:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "proposal_id": "proposal-001", "asset": "BTC/USD", "correlated_group": "BTC-beta",
        "direction": Direction.LONG, "as_of": now, "quote_observed_at": now - timedelta(seconds=5),
        "data_verified": True, "data_quality": Decimal("0.99"), "equity": Decimal("10000"),
        "daily_pnl": Decimal("0"), "peak_equity": Decimal("10000"), "open_positions": (),
        "requested_notional": Decimal("1000"), "entry": Decimal("100"), "stop_loss": Decimal("95"),
        "take_profit": Decimal("110"), "spread_fraction": Decimal("0.001"),
        "expected_slippage_fraction": Decimal("0.0005"),
    }
    values.update(overrides)
    return RiskEvaluationRequest.model_validate(values)

def test_safe_proposal_passes_but_never_authorizes_execution() -> None:
    result = IndependentRiskGate(policy()).evaluate(request())
    assert result.disposition is RiskDisposition.APPROVED
    assert result.approved_notional == Decimal("1000")
    assert result.risk_amount == Decimal("50")
    assert result.reward_risk_ratio == Decimal("2")
    assert result.execution_authorized is False
    assert result.risk_engine_version == ENGINE_VERSION
    assert result.invalidation_conditions

@pytest.mark.parametrize(("changes", "check"), [
    ({"data_verified": False}, "verified_market_data"),
    ({"data_quality": Decimal("0.5")}, "data_quality"),
    ({"quote_observed_at": datetime(2026, 10, 10, 11, 0, tzinfo=UTC)}, "quote_freshness"),
    ({"stop_loss": Decimal("105")}, "stop_loss_and_take_profit"),
    ({"take_profit": Decimal("105")}, "risk_reward"),
    ({"requested_notional": Decimal("3000")}, "risk_per_trade"),
    ({"daily_pnl": Decimal("-300")}, "daily_loss"),
    ({"equity": Decimal("8000"), "peak_equity": Decimal("10000")}, "drawdown"),
    ({"spread_fraction": Decimal("0.01")}, "spread"),
    ({"expected_slippage_fraction": Decimal("0.01")}, "slippage"),
])
def test_hard_gate_rejects_each_invalid_condition(changes: dict[str, object], check: str) -> None:
    result = IndependentRiskGate(policy()).evaluate(request(**changes))
    assert result.disposition is RiskDisposition.REJECTED
    assert result.approved_notional == 0
    assert result.execution_authorized is False
    assert any(item.name == check and not item.passed for item in result.checks)
    assert result.rejection_reasons

def test_correlated_and_open_position_limits_are_enforced() -> None:
    positions = (
        OpenPosition(asset="ETH/USD", notional=Decimal("2000"), correlated_group="BTC-beta", direction=Direction.LONG),
        OpenPosition(asset="SOL/USD", notional=Decimal("2000"), correlated_group="BTC-beta", direction=Direction.LONG),
    )
    result = IndependentRiskGate(policy()).evaluate(request(open_positions=positions))
    assert result.disposition is RiskDisposition.REJECTED
    failed = {item.name for item in result.checks if not item.passed}
    assert "correlated_position_count" in failed
    assert "correlated_exposure" in failed

def test_daily_loss_limit_is_hard_stop_at_threshold() -> None:
    result = IndependentRiskGate(policy()).evaluate(request(daily_pnl=Decimal("-300")))
    assert result.disposition is RiskDisposition.REJECTED
    assert "daily_loss" in {item.name for item in result.checks if not item.passed}

def test_short_proposal_requires_stop_above_and_target_below_entry() -> None:
    result = IndependentRiskGate(policy()).evaluate(request(
        direction=Direction.SHORT, stop_loss=Decimal("105"), take_profit=Decimal("90")))
    assert result.disposition is RiskDisposition.APPROVED

def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        IndependentRiskGate(policy()).evaluate(request(as_of=datetime(2026, 10, 10, 12, 0)))
