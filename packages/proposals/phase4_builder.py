from datetime import datetime
from decimal import Decimal

from contracts.domain import RiskDecision, RiskDecisionRecord, TradeProposal
from contracts.phase4_risk import RiskDecisionResult, RiskDisposition, RiskEvaluationRequest
from contracts.signal import SignalRecord


class Phase4TradeProposalBuilder:
    """Creates a reviewable proposal only from a passing independent Phase 4 decision."""

    version = "phase4-proposal-builder-1.0.0"

    def build(
        self,
        signal: SignalRecord,
        request: RiskEvaluationRequest,
        decision: RiskDecisionResult,
        *,
        venue: str,
        regime: str,
        mtf_alignment: Decimal,
        model_versions: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> TradeProposal:
        observed_at = now or request.as_of
        if observed_at.tzinfo is None:
            raise ValueError("proposal timestamp must be timezone-aware")
        if observed_at >= signal.expires_at:
            raise ValueError("cannot create a proposal from an expired signal")
        if decision.disposition is not RiskDisposition.APPROVED:
            raise ValueError("independent risk decision rejected; proposal creation blocked")
        if decision.execution_authorized:
            raise ValueError("risk decision must never authorize execution")
        if decision.proposal_id != request.proposal_id or request.proposal_id != str(signal.id):
            raise ValueError("risk decision, request, and signal identifiers must match")
        if signal.asset != request.asset or signal.direction != request.direction:
            raise ValueError("risk request must match the signal asset and direction")
        if decision.approved_notional <= 0:
            raise ValueError("approved risk decision must contain a positive notional")
        if decision.approved_notional != request.requested_notional:
            raise ValueError("approved notional does not match the risk-evaluated request")
        if not 0 <= mtf_alignment <= 1:
            raise ValueError("MTF alignment must be between 0 and 1")
        if not request.data_verified:
            raise ValueError("verified market data is required")

        risk_record = RiskDecisionRecord(
            decision=RiskDecision.APPROVED,
            reasons=("All independent Phase 4 risk checks passed.",),
            evaluated_at=decision.evaluated_at,
            risk_engine_version=decision.risk_engine_version,
        )
        return TradeProposal(
            id=signal.id,
            asset=signal.asset,
            venue=venue,
            direction=signal.direction,
            created_at=observed_at,
            expires_at=signal.expires_at,
            entry=request.entry,
            stop=request.stop_loss,
            target=request.take_profit,
            risk_reward=decision.reward_risk_ratio,
            position_size=decision.approved_notional,
            strategy_votes=signal.strategy_votes,
            mtf_alignment=mtf_alignment,
            regime=regime,
            model_versions=model_versions,
            data_quality=request.data_quality,
            evidence=(),
            risk=risk_record,
            provenance=(),
            invalidation_conditions=decision.invalidation_conditions,
        )
