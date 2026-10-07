from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.market_data.contracts import Candle, MarketDataRequest
from packages.market_data.ingestion import MarketDataIngestor
from packages.market_data.verification import MarketDataVerificationError, verify_series


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def make_candle(offset_minutes: int = 0) -> Candle:
    close_time = NOW - timedelta(minutes=offset_minutes)
    return Candle(
        asset="BTC/USD",
        venue="spot",
        timeframe="1h",
        open_time=close_time - timedelta(hours=1),
        close_time=close_time,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        provider="test",
        provider_version="1",
        observed_at=close_time,
        received_at=NOW,
    )


def test_future_candle_fails_closed() -> None:
    with pytest.raises(MarketDataVerificationError):
        verify_series(
            [make_candle(-1)],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=120,
        )


def test_stale_candle_fails_closed() -> None:
    with pytest.raises(MarketDataVerificationError):
        verify_series(
            [make_candle(121)],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=120,
        )


def test_duplicate_candles_are_deterministically_removed() -> None:
    candles = verify_series(
        [make_candle(), make_candle()],
        now=NOW,
        interval=timedelta(hours=1),
        max_age_seconds=120,
    )
    assert len(candles) == 1
    assert candles[0].quality.value == "VERIFIED"


class Provider:
    id = "test"
    version = "1"

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = candles

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        return self._candles

    async def quote(self, request: MarketDataRequest):
        raise NotImplementedError

    async def health(self):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_ingestor_fails_over_when_primary_data_is_invalid() -> None:
    primary = Provider([make_candle(121)])
    secondary = Provider([make_candle()])
    result = await MarketDataIngestor([primary, secondary]).candles(
        MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
        now=NOW,
    )
    assert result[0].provider == "test"
    assert result[0].request_id is not None
