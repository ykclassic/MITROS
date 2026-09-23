from decimal import Decimal

from contracts.risk import PortfolioState, RiskAssessment, RiskCheck, RiskLimits


class AdvancedRiskEngine:
    """Independent portfolio risk gate. Never authorizes execution."""

    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def assess(
        self,
        portfolio: PortfolioState,
        asset: str,
        requested_size: Decimal,
        stop_distance_fraction: Decimal,
        spread_fraction: Decimal = Decimal("0"),
    ) -> RiskAssessment:
        if requested_size <= 0 or stop_distance_fraction <= 0 or spread_fraction < 0:
            raise ValueError("risk inputs must be positive")
        checks = tuple(RiskCheck)
        proposed_fraction = requested_size / portfolio.equity
        existing_asset = sum((p.market_value for p in portfolio.positions if p.asset == asset), Decimal("0"))
        concentration = (existing_asset + requested_size) / portfolio.equity
        projected_exposure = portfolio.gross_exposure + proposed_fraction
        daily_loss = max(Decimal("0"), -portfolio.daily_pnl) / portfolio.equity
        leverage = projected_exposure
        failures: list[str] = []
        if proposed_fraction > self.limits.max_position_fraction:
            failures.append("position size limit exceeded")
        if projected_exposure > self.limits.max_gross_exposure:
            failures.append("gross exposure limit exceeded")
        if daily_loss > self.limits.max_daily_loss_fraction:
            failures.append("daily loss limit exceeded")
        if concentration > self.limits.max_concentration_fraction:
            failures.append("asset concentration limit exceeded")
        if leverage > self.limits.max_leverage:
            failures.append("leverage limit exceeded")
        if portfolio.drawdown > self.limits.max_drawdown_fraction:
            failures.append("drawdown limit exceeded")
        if spread_fraction > self.limits.max_spread_fraction:
            failures.append("spread limit exceeded")
        approved = not failures
        risk_score = min(Decimal("1"), max(proposed_fraction, daily_loss, portfolio.drawdown))
        return RiskAssessment(
            approved=approved,
            requested_size=requested_size,
            approved_size=requested_size if approved else Decimal("0"),
            checks=checks,
            reasons=tuple(failures) if failures else ("all risk checks passed",),
            risk_score=risk_score,
        )
