from datetime import datetime
from decimal import Decimal

from contracts.domain import (
    Evidence,
    RiskDecision,
    RiskDecisionRecord,
    TradeProposal,
)
from contracts.risk import RiskAssessment
from contracts.signal import SignalRecord


class TradeProposalBuilder:
    """Builds executable-intent proposals from a live signal and an approved risk result.

    This component never submits orders and never grants human approval.
    """

    version = "1.0.0"

    def build(
        self,
        signal: SignalRecord,
        risk: RiskAssessment,
        *,
        entry: Decimal,
        stop: Decimal,
        target: Decimal,
        regime: str,
        mtf_alignment: Decimal,
        data_quality: Decimal,
        evidence: tuple[Evidence, ...] = (),
        model_versions: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> TradeProposal:
        observed_at = now or signal.created_at
        if observed_at >= signal.expires_at:
            raise ValueError("cannot create a proposal from an expired signal")
        if signal.direction is None:
            raise ValueError("trade proposal requires a directional signal")
        if not risk.approved or risk.approved_size <= 0:
            raise ValueError("trade proposal requires an approved risk assessment")
        if entry <= 0 or stop <= 0 or target <= 0:
            raise ValueError("entry, stop, and target must be positive")
        if signal.direction.value == "LONG":
            valid_levels = stop < entry < target
        else:
            valid_levels = stop > entry > target
        if not valid_levels:
            raise ValueError("price levels are inconsistent with signal direction")
        if not 0 <= mtf_alignment <= 1 or not 0 <= data_quality <= 1:
            raise ValueError("alignment and data quality must be between 0 and 1")

        reward = abs(target - entry)
        risk_distance = abs(entry - stop)
        risk_reward = reward / risk_distance
        risk_record = RiskDecisionRecord(
            decision=RiskDecision.APPROVED,
            reasons=risk.reasons,
            evaluated_at=observed_at,
            risk_engine_version="advanced-risk@1.0.0",
        )
        return TradeProposal(
            asset=signal.asset,
            venue=signal.venue,
            direction=signal.direction,
            created_at=observed_at,
            expires_at=signal.expires_at,
            entry=entry,
            stop=stop,
            target=target,
            risk_reward=risk_reward,
            position_size=risk.approved_size,
            strategy_votes=signal.strategy_votes,
            mtf_alignment=mtf_alignment,
            regime=regime,
            model_versions=model_versions,
            data_quality=data_quality,
            evidence=evidence,
            risk=risk_record,
            provenance=(),
        )
