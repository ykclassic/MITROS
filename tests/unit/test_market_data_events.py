from datetime import UTC,datetime
from decimal import Decimal
from uuid import uuid4
from packages.market_data.contracts import Candle
from packages.market_data.events import market_data_event

def test_market_data_event_contains_provider_provenance():
    now=datetime.now(UTC)
    candle=Candle(asset="BTC/USD",venue="spot",timeframe="1h",open_time=now,close_time=now,
        open=Decimal("1"),high=Decimal("2"),low=Decimal("1"),close=Decimal("1.5"),
        provider="twelvedata",provider_version="v1",observed_at=now,received_at=now)
    event=market_data_event(candle,aggregate_id=uuid4(),correlation_id=uuid4())
    assert event.event_type.value=="MarketDataUpdated"
    assert event.provenance[0]["source"]=="twelvedata"
