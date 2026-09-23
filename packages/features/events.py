from datetime import UTC, datetime
from uuid import UUID
from contracts.events import EventEnvelope, EventType
from contracts.features import FeatureSnapshot

def features_computed_event(snapshot: FeatureSnapshot, *, aggregate_id: UUID, correlation_id: UUID) -> EventEnvelope:
    return EventEnvelope(
        event_type=EventType.FEATURES_COMPUTED,
        aggregate_id=aggregate_id,
        occurred_at=snapshot.as_of,
        recorded_at=datetime.now(UTC),
        producer="feature-engine",
        producer_version=snapshot.feature_set_version,
        correlation_id=correlation_id,
        payload={
            "asset": snapshot.asset,
            "venue": snapshot.venue,
            "timeframe": snapshot.timeframe,
            "as_of": snapshot.as_of.isoformat(),
            "feature_set_version": snapshot.feature_set_version,
            "features": {key: str(value) for key, value in snapshot.values.items()},
        },
        provenance=[{
            "source": item.source,
            "source_version": item.source_version,
            "observed_at": item.observed_at.isoformat(),
            "received_at": item.received_at.isoformat(),
        } for item in snapshot.provenance],
    )
