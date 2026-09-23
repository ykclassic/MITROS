from datetime import UTC,datetime
from uuid import UUID
from contracts.events import EventEnvelope,EventType
from .contracts import Candle

def market_data_event(candle:Candle,*,aggregate_id:UUID,correlation_id:UUID)->EventEnvelope:
    return EventEnvelope(
        event_type=EventType.MARKET_DATA_UPDATED,
        aggregate_id=aggregate_id,
        occurred_at=candle.observed_at,
        recorded_at=datetime.now(UTC),
        producer=f"market-data:{candle.provider}",
        producer_version=candle.provider_version or "unknown",
        correlation_id=correlation_id,
        payload={"asset":candle.asset,"venue":candle.venue,"timeframe":candle.timeframe,"open_time":candle.open_time.isoformat(),"close":str(candle.close)},
        provenance=[{"source":candle.provider,"source_version":candle.provider_version,"observed_at":candle.observed_at.isoformat(),"received_at":candle.received_at.isoformat()}],
    )
