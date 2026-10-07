from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.market_data.contracts import Candle, MarketDataRequest
from packages.market_data.ingestion import MarketDataIngestor
from packages.market_data.service import VerifiedMarketDataService


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


class Provider:
    id = "test"
    version = "1"

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        close_time = NOW
        return [
            Candle(
                asset=request.asset,
                venue=request.venue,
                timeframe=request.timeframe or "1h",
                open_time=close_time - timedelta(hours=1),
                close_time=close_time,
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                provider=self.id,
                provider_version=self.version,
                observed_at=close_time,
                received_at=NOW,
            )
        ]

    async def quote(self, request: MarketDataRequest):
        raise NotImplementedError

    async def health(self):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_verified_service_emits_market_data_updated() -> None:
    service = VerifiedMarketDataService(
        MarketDataIngestor([Provider()], freshness_seconds=120),
        producer_version="phase1-test",
    )
    batch = await service.candles(
        MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
        now=NOW,
    )

    assert len(batch.candles) == 1
    assert batch.candles[0].quality.value == "VERIFIED"
    assert batch.candles[0].request_id is not None
    assert batch.event.event_type.value == "MarketDataUpdated"
    assert batch.event.payload["checksum"]
