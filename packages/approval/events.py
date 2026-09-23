from datetime import datetime, timezone
from uuid import UUID

from contracts.approval import ApprovalDecision, ApprovalOutcome
from contracts.events import EventEnvelope, EventType


def _approval_event(
    outcome: ApprovalOutcome,
    *,
    event_type: EventType,
    correlation_id: UUID,
    recorded_at: datetime | None,
) -> EventEnvelope:
    recorded = recorded_at or datetime.now(timezone.utc)
    return EventEnvelope(
        event_type=event_type,
        aggregate_id=outcome.proposal_id,
        occurred_at=outcome.approval.decided_at,
        recorded_at=recorded,
        producer="human-approval",
        producer_version="1.0.0",
        correlation_id=correlation_id,
        payload={
            "approval_id": str(outcome.approval.id),
            "actor": outcome.approval.actor,
            "decision": outcome.approval.decision.value,
            "idempotency_key": outcome.approval.idempotency_key,
            "reason": outcome.approval.reason,
        },
        provenance=[{"source": "human-approval-manager", "version": "1.0.0"}],
    )


def approval_granted_event(
    outcome: ApprovalOutcome,
    *,
    correlation_id: UUID,
    recorded_at: datetime | None = None,
) -> EventEnvelope:
    if outcome.decision is not ApprovalDecision.APPROVED:
        raise ValueError("only an approved outcome can produce ApprovalGranted")
    return _approval_event(
        outcome,
        event_type=EventType.APPROVAL_GRANTED,
        correlation_id=correlation_id,
        recorded_at=recorded_at,
    )


def approval_rejected_event(
    outcome: ApprovalOutcome,
    *,
    correlation_id: UUID,
    recorded_at: datetime | None = None,
) -> EventEnvelope:
    if outcome.decision is not ApprovalDecision.REJECTED:
        raise ValueError("only a rejected outcome can produce ApprovalRejected")
    return _approval_event(
        outcome,
        event_type=EventType.APPROVAL_REJECTED,
        correlation_id=correlation_id,
        recorded_at=recorded_at,
    )
