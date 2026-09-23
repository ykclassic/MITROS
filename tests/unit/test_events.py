from datetime import UTC, datetime
from uuid import uuid4

from contracts.events import EventEnvelope, EventType


def test_event_envelope_defaults() -> None:
    now = datetime.now(UTC)
    event = EventEnvelope(
        event_type=EventType.MARKET_DATA_UPDATED,
        aggregate_id=uuid4(),
        occurred_at=now,
        recorded_at=now,
        producer="test",
        producer_version="0.1",
        correlation_id=uuid4(),
        payload={},
        provenance=[],
    )
    assert event.schema_version == 1
