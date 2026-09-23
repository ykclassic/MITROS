from datetime import datetime,timezone
from uuid import uuid4
from contracts.events import EventEnvelope,EventType
def test_event_envelope_defaults():
    now=datetime.now(timezone.utc)
    e=EventEnvelope(event_type=EventType.MARKET_DATA_UPDATED,aggregate_id=uuid4(),occurred_at=now,recorded_at=now,producer="test",producer_version="0.1",correlation_id=uuid4(),payload={},provenance=[])
    assert e.schema_version==1
