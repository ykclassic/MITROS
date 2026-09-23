from datetime import UTC, datetime
from uuid import UUID

from contracts.domain import StrategyVote
from contracts.events import EventEnvelope, EventType

def strategy_signal_generated_event(
    vote: StrategyVote,
    *,
    aggregate_id: UUID,
    correlation_id: UUID,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=EventType.STRATEGY_SIGNAL_GENERATED,
        aggregate_id=aggregate_id,
        occurred_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
        producer=vote.strategy_id,
        producer_version=vote.strategy_version,
        correlation_id=correlation_id,
        payload={
            "strategy_id": vote.strategy_id,
            "strategy_version": vote.strategy_version,
            "direction": vote.direction.value if vote.direction is not None else None,
            "confidence": str(vote.confidence),
            "reasons": list(vote.reasons),
        },
        provenance=[],
    )
