from decimal import Decimal
from contracts.phase4_risk import RiskCheckResult, RiskDecisionResult, RiskDisposition, RiskEvaluationRequest, RiskPolicy

ENGINE_VERSION = "phase4-independent-risk-1.0.0"
ZERO = Decimal("0")

class IndependentRiskGate:
    """Deterministic hard gate for trade proposals; has no execution capability."""
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy

    def evaluate(self, request: RiskEvaluationRequest) -> RiskDecisionResult:
        if request.as_of.tzinfo is None or request.quote_observed_at.tzinfo is None:
            raise ValueError("proposal and quote timestamps must be timezone-aware")
        if request.peak_equity < request.equity:
            raise ValueError("peak_equity must be greater than or equal to equity")
        if request.daily_pnl > request.equity:
            raise ValueError("daily_pnl is inconsistent with equity")

        direction = request.direction.value
        levels_valid = (
            request.stop_loss < request.entry < request.take_profit
            if direction == "LONG"
            else request.take_profit < request.entry < request.stop_loss
        )
        stop_distance = abs(request.entry - request.stop_loss) / request.entry
        reward_distance = abs(request.take_profit - request.entry) / request.entry
        rr = reward_distance / stop_distance if stop_distance > ZERO else ZERO
        risk_amount = request.requested_notional * stop_distance
        risk_fraction = risk_amount / request.equity
        requested_fraction = request.requested_notional / request.equity
        daily_loss = max(ZERO, -request.daily_pnl) / request.equity
        drawdown = max(ZERO, request.peak_equity - request.equity) / request.peak_equity
        gross_notional = sum((p.notional for p in request.open_positions), ZERO)
        gross_fraction = (gross_notional + request.requested_notional) / request.equity
        asset_notional = sum((p.notional for p in request.open_positions if p.asset == request.asset), ZERO)
        concentration = (asset_notional + request.requested_notional) / request.equity
        correlated_positions = sum(1 for p in request.open_positions if p.correlated_group == request.correlated_group)
        correlated_notional = sum((p.notional for p in request.open_positions if p.correlated_group == request.correlated_group), ZERO)
        correlated_fraction = (correlated_notional + request.requested_notional) / request.equity
        quote_age_seconds = (request.as_of - request.quote_observed_at).total_seconds()
        quote_fresh = 0 <= quote_age_seconds <= self.policy.max_quote_age_seconds
        quote_age = Decimal(str(max(0, quote_age_seconds)))

        checks = (
            RiskCheckResult(name="verified_market_data", passed=request.data_verified, observed=request.data_verified, threshold=True, reason="Market data must be verified by the authoritative data pipeline."),
            RiskCheckResult(name="quote_freshness", passed=quote_fresh, observed=quote_age, threshold=Decimal(self.policy.max_quote_age_seconds), reason="Quote must not be from the future or older than the policy permits."),
            RiskCheckResult(name="data_quality", passed=request.data_quality >= self.policy.min_data_quality, observed=request.data_quality, threshold=self.policy.min_data_quality, reason="Data quality must meet the configured minimum."),
            RiskCheckResult(name="stop_loss_and_take_profit", passed=levels_valid, observed=f"{request.entry}/{request.stop_loss}/{request.take_profit}", threshold="directionally valid entry/stop/target", reason="Stop-loss and take-profit are mandatory and must be on the correct side of entry."),
            RiskCheckResult(name="risk_reward", passed=rr >= self.policy.min_risk_reward, observed=rr, threshold=self.policy.min_risk_reward, reason="Reward-to-risk ratio must meet the policy minimum."),
            RiskCheckResult(name="risk_per_trade", passed=risk_fraction <= self.policy.max_risk_per_trade, observed=risk_fraction, threshold=self.policy.max_risk_per_trade, reason="Stop-based loss at requested size must fit the risk budget."),
            RiskCheckResult(name="position_size", passed=requested_fraction <= self.policy.max_position_fraction, observed=requested_fraction, threshold=self.policy.max_position_fraction, reason="Requested notional must fit the per-position size cap."),
            RiskCheckResult(name="gross_exposure", passed=gross_fraction <= self.policy.max_gross_exposure_fraction, observed=gross_fraction, threshold=self.policy.max_gross_exposure_fraction, reason="Existing plus proposed gross exposure must fit the portfolio cap."),
            RiskCheckResult(name="daily_loss", passed=daily_loss < self.policy.max_daily_loss_fraction, observed=daily_loss, threshold=self.policy.max_daily_loss_fraction, reason="Daily loss at or above the hard limit blocks new risk."),
            RiskCheckResult(name="drawdown", passed=drawdown < self.policy.max_drawdown_fraction, observed=drawdown, threshold=self.policy.max_drawdown_fraction, reason="Drawdown at or above the hard limit blocks new risk."),
            RiskCheckResult(name="asset_concentration", passed=concentration <= self.policy.max_asset_concentration_fraction, observed=concentration, threshold=self.policy.max_asset_concentration_fraction, reason="Same-asset exposure must fit the concentration cap."),
            RiskCheckResult(name="correlated_position_count", passed=correlated_positions < self.policy.max_correlated_positions, observed=correlated_positions + 1, threshold=self.policy.max_correlated_positions, reason="Proposal would exceed the maximum correlated open positions."),
            RiskCheckResult(name="correlated_exposure", passed=correlated_fraction <= self.policy.max_correlated_exposure_fraction, observed=correlated_fraction, threshold=self.policy.max_correlated_exposure_fraction, reason="Correlated group exposure must fit its hard cap."),
            RiskCheckResult(name="open_position_count", passed=len(request.open_positions) < self.policy.max_open_positions, observed=len(request.open_positions) + 1, threshold=self.policy.max_open_positions, reason="Proposal would exceed the maximum open positions."),
            RiskCheckResult(name="spread", passed=request.spread_fraction <= self.policy.max_spread_fraction, observed=request.spread_fraction, threshold=self.policy.max_spread_fraction, reason="Current spread must be within the configured maximum."),
            RiskCheckResult(name="slippage", passed=request.expected_slippage_fraction <= self.policy.max_slippage_fraction, observed=request.expected_slippage_fraction, threshold=self.policy.max_slippage_fraction, reason="Expected slippage must be within the configured maximum."),
        )
        rejections = tuple(check.reason for check in checks if not check.passed)
        approved = not rejections
        return RiskDecisionResult(
            proposal_id=request.proposal_id,
            disposition=RiskDisposition.APPROVED if approved else RiskDisposition.REJECTED,
            approved_notional=request.requested_notional if approved else ZERO,
            risk_amount=risk_amount if approved else ZERO,
            risk_fraction=risk_fraction if approved else ZERO,
            reward_risk_ratio=rr,
            checks=checks,
            rejection_reasons=rejections,
            invalidation_conditions=(
                f"Invalidate {direction} proposal if a verified price reaches or crosses stop-loss {request.stop_loss}.",
                "Invalidate when the proposal expires or its market-data evidence becomes stale or unverified.",
                "Invalidate if spread, expected slippage, portfolio exposure, daily loss, or drawdown breaches policy before approval.",
            ),
            evaluated_at=request.as_of,
            risk_engine_version=ENGINE_VERSION,
            execution_authorized=False,
        )
