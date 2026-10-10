from datetime import datetime, timezone
from uuid import UUID

from contracts.events import EventEnvelope, EventType
from contracts.phase4_risk import RiskDecisionResult


def risk_decision_event(
    decision: RiskDecisionResult,
    *,
    aggregate_id: UUID,
    correlation_id: UUID,
    recorded_at: datetime | None = None,
) -> EventEnvelope:
    """Create an immutable audit event for an independent risk decision."""
    recorded = recorded_at or datetime.now(timezone.utc)
    return EventEnvelope(
        event_type=EventType.RISK_EVALUATED,
        aggregate_id=aggregate_id,
        occurred_at=decision.evaluated_at,
        recorded_at=recorded,
        producer="phase4-independent-risk",
        producer_version=decision.risk_engine_version,
        correlation_id=correlation_id,
        payload={
            "proposal_id": decision.proposal_id,
            "disposition": decision.disposition.value,
            "approved_notional": str(decision.approved_notional),
            "risk_amount": str(decision.risk_amount),
            "risk_fraction": str(decision.risk_fraction),
            "reward_risk_ratio": str(decision.reward_risk_ratio),
            "execution_authorized": decision.execution_authorized,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "observed": str(check.observed),
                    "threshold": str(check.threshold),
                    "reason": check.reason,
                }
                for check in decision.checks
            ],
            "rejection_reasons": list(decision.rejection_reasons),
            "invalidation_conditions": list(decision.invalidation_conditions),
        },
        provenance=[{"source": "independent-risk-gate", "version": decision.risk_engine_version}],
    )
