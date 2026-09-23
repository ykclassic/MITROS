from datetime import datetime, timezone
from uuid import UUID

from contracts.approval import ApprovalOutcome
from contracts.events import EventEnvelope, EventType


def approval_granted_event(
    outcome: ApprovalOutcome,
    *,
    correlation_id: UUID,
    recorded_at: datetime | None = None,
) -> EventEnvelope:
    if not outcome.execution_authorized or outcome.approval.approval_token is None:
        raise ValueError("only an approved outcome can produce ApprovalGranted")
    recorded = recorded_at or datetime.now(timezone.utc)
    return EventEnvelope(
        event_type=EventType.APPROVAL_GRANTED,
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
            "approval_token": outcome.approval.approval_token,
            "idempotency_key": outcome.approval.idempotency_key,
        },
        provenance=[{"source": "human-approval-manager", "version": "1.0.0"}],
    )
