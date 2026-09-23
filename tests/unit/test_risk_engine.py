from decimal import Decimal

import pytest

from contracts.risk import PortfolioState, PositionState, RiskLimits
from packages.risk.engine import AdvancedRiskEngine


def portfolio() -> PortfolioState:
    return PortfolioState(
        equity=Decimal("100000"), balance=Decimal("100000"), daily_pnl=Decimal("0"),
        peak_equity=Decimal("100000"),
        positions=(PositionState(asset="BTC/USD", market_value=Decimal("10000"), unrealized_pnl=Decimal("0"), direction="LONG"),),
    )


def limits() -> RiskLimits:
    return RiskLimits(
        max_position_fraction=Decimal("0.02"), max_gross_exposure=Decimal("1.0"),
        max_daily_loss_fraction=Decimal("0.03"), max_drawdown_fraction=Decimal("0.10"),
        max_concentration_fraction=Decimal("0.10"), max_leverage=Decimal("1.0"),
        max_spread_fraction=Decimal("0.01"),
    )


def test_risk_approves_safe_position():
    result = AdvancedRiskEngine(limits()).assess(portfolio(), "ETH/USD", Decimal("1000"), Decimal("0.02"))
    assert result.approved
    assert result.approved_size == Decimal("1000")


def test_risk_rejects_oversized_position():
    result = AdvancedRiskEngine(limits()).assess(portfolio(), "ETH/USD", Decimal("3000"), Decimal("0.02"))
    assert not result.approved
    assert result.approved_size == Decimal("0")


def test_risk_rejects_daily_loss():
    p = portfolio().model_copy(update={"daily_pnl": Decimal("-4000")})
    result = AdvancedRiskEngine(limits()).assess(p, "ETH/USD", Decimal("1000"), Decimal("0.02"))
    assert not result.approved


def test_risk_rejects_drawdown():
    p = portfolio().model_copy(update={"equity": Decimal("89000"), "peak_equity": Decimal("100000")})
    result = AdvancedRiskEngine(limits()).assess(p, "ETH/USD", Decimal("1000"), Decimal("0.02"))
    assert not result.approved


def test_risk_rejects_spread():
    result = AdvancedRiskEngine(limits()).assess(portfolio(), "ETH/USD", Decimal("1000"), Decimal("0.02"), Decimal("0.02"))
    assert not result.approved


def test_risk_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        AdvancedRiskEngine(limits()).assess(portfolio(), "ETH/USD", Decimal("0"), Decimal("0.02"))
