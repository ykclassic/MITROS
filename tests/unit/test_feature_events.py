from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from contracts.features import FeatureSnapshot
from packages.features.events import features_computed_event
from contracts.events import EventType
from contracts.domain import Provenance

def test_features_event_contains_versioned_features_and_provenance():
    now = datetime.now(UTC)
    snapshot = FeatureSnapshot(
        asset="BTC/USD",
        venue="spot",
        timeframe="1h",
        as_of=now,
        feature_set_version="1.0.0",
        values={"sma_20": Decimal("100.5")},
        required_history=50,
        provenance=(Provenance(
            source="twelvedata",
            source_version="v1",
            observed_at=now,
            received_at=now,
        ),),
    )
    event = features_computed_event(snapshot, aggregate_id=uuid4(), correlation_id=uuid4())
    assert event.event_type is EventType.FEATURES_COMPUTED
    assert event.producer == "feature-engine"
    assert event.payload["feature_set_version"] == "1.0.0"
    assert event.payload["features"]["sma_20"] == "100.5"
    assert event.provenance[0]["source"] == "twelvedata"
