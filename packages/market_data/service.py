from datetime import UTC, datetime
from uuid import uuid4
from typing import Any

from contracts.events import EventEnvelope, EventType

from .checksum import canonical_checksum
from .contracts import Candle, MarketDataRequest, ObservationManifestEntry
from .guards import require_verified
from .ingestion import MarketDataIngestor
from .timeframes import timeframe_delta
from .verification import build_manifest


class VerifiedMarketDataBatch:
    def __init__(
        self,
        *,
        candles: tuple[Candle, ...],
        event: EventEnvelope,
        manifest: tuple[ObservationManifestEntry, ...],
        batch_checksum: str,
    ) -> None:
        self.candles = candles
        self.event = event
        self.manifest = manifest
        self.batch_checksum = batch_checksum


class VerifiedMarketDataService:
    """Fail-closed Phase 1 boundary for canonical, provenance-bearing candles."""

    def __init__(
        self, ingestor: MarketDataIngestor, *, producer_version: str,
        persistence: Any | None = None,
    ) -> None:
        self.ingestor = ingestor
        self.producer_version = producer_version
        self.persistence = persistence

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
        verified = require_verified(result)
        manifest = build_manifest(list(verified))
        batch_checksum = canonical_checksum(
            [item.model_dump(mode="json") for item in manifest]
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
                "count": len(verified),
                "first_open_time": verified[0].open_time.isoformat(),
                "last_close_time": verified[-1].close_time.isoformat(),
                "checksum": batch_checksum,
                "manifest_count": len(manifest),
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
                for item in verified
            ],
        )
        batch = VerifiedMarketDataBatch(
            candles=verified,
            event=event,
            manifest=manifest,
            batch_checksum=batch_checksum,
        )
        if self.persistence is not None:
            await self.persistence.persist_candles(
                verified, batch_checksum=batch_checksum, manifest=manifest
            )
        return batch
