from datetime import UTC, datetime
from uuid import uuid4

from contracts.events import EventEnvelope, EventType

from .checksum import canonical_checksum
from .contracts import Candle, MarketDataRequest
from .ingestion import MarketDataIngestor
from .timeframes import timeframe_delta


class VerifiedMarketDataBatch:
    def __init__(self, *, candles: tuple[Candle, ...], event: EventEnvelope) -> None:
        self.candles = candles
        self.event = event


class VerifiedMarketDataService:
    """Fail-closed Phase 1 boundary for canonical, provenance-bearing candles."""

    def __init__(self, ingestor: MarketDataIngestor, *, producer_version: str) -> None:
        self.ingestor = ingestor
        self.producer_version = producer_version

    async def candles(
        self,
        request: MarketDataRequest,
        *,
        now: datetime | None = None,
    ) -> VerifiedMarketDataBatch:
        reference = (now or datetime.now(UTC)).astimezone(UTC)
        timeframe = request.timeframe or "1h"
        result = await self.ingestor.candles(
            request,
            interval=timeframe_delta(timeframe),
            now=reference,
        )
        if not result:
            raise RuntimeError("Verified market-data service received no candles")

        checksum = canonical_checksum(
            [
                {
                    "asset": item.asset,
                    "venue": item.venue,
                    "timeframe": item.timeframe,
                    "open_time": item.open_time.isoformat(),
                    "close_time": item.close_time.isoformat(),
                    "open": item.open,
                    "high": item.high,
                    "low": item.low,
                    "close": item.close,
                    "volume": item.volume,
                }
                for item in result
            ]
        )
        event_id = uuid4()
        event = EventEnvelope(
            id=event_id,
            event_type=EventType.MARKET_DATA_UPDATED,
            aggregate_id=event_id,
            occurred_at=reference,
            recorded_at=reference,
            producer="mitros.market_data",
            producer_version=self.producer_version,
            correlation_id=event_id,
            payload={
                "asset": request.asset,
                "venue": request.venue,
                "timeframe": timeframe,
                "count": len(result),
                "first_open_time": result[0].open_time.isoformat(),
                "last_close_time": result[-1].close_time.isoformat(),
                "checksum": checksum,
            },
            provenance=[
                {
                    "source": item.provider,
                    "source_version": item.provider_version,
                    "observed_at": item.observed_at,
                    "received_at": item.received_at,
                    "request_id": item.request_id,
                    "checksum": item.checksum,
                }
                for item in result
            ],
        )
        return VerifiedMarketDataBatch(candles=tuple(result), event=event)
