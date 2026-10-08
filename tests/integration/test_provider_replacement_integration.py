from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.market_data.contracts import Candle, DataQuality, MarketDataRequest
from packages.market_data.ingestion import MarketDataIngestor
from packages.market_data.routing import ProviderRoute, StaticProviderConfiguration
from packages.market_data.verification import MarketDataVerificationError


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def candle(provider: str, close: str = "105") -> Candle:
    end = NOW
    return Candle(
        asset="BTC/USD",
        venue="spot",
        symbol="BTC/USD",
        timeframe="1h",
        open_time=end - timedelta(hours=1),
        close_time=end,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal(close),
        provider=provider,
        provider_version="1",
        observed_at=end,
        received_at=NOW,
    )


class StubProvider:
    def __init__(self, provider_id: str, rows: list[Candle]) -> None:
        self.id = provider_id
        self.version = "1"
        self.rows = rows

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        return self.rows

    async def quote(self, request: MarketDataRequest):
        raise NotImplementedError

    async def health(self):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_kraken_primary_cross_validates_coinbase_with_tolerance() -> None:
    kraken = StubProvider("kraken", [candle("kraken", close="105")])
    coinbase = StubProvider("coinbase", [candle("coinbase", close="105.50")])
    config = StaticProviderConfiguration(
        (
            ProviderRoute("kraken", "v1", 1, "PRIMARY", True, True, ("1h",), ("spot",)),
            ProviderRoute("coinbase", "v1", 2, "SECONDARY", True, True, ("1h",), ("spot",)),
        )
    )
    result = await MarketDataIngestor(
        [kraken, coinbase],
        configuration=config,
        cross_validation_tolerance=Decimal("0.01"),
    ).candles(
        MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
        now=NOW,
    )
    assert result[0].provider == "kraken"
    assert result[0].quality is DataQuality.VERIFIED


@pytest.mark.asyncio
async def test_cross_provider_conflict_still_fails_closed() -> None:
    kraken = StubProvider("kraken", [candle("kraken", close="105")])
    coinbase = StubProvider("coinbase", [candle("coinbase", close="110")])
    config = StaticProviderConfiguration(
        (
            ProviderRoute("kraken", "v1", 1, "PRIMARY", True, True, ("1h",), ("spot",)),
            ProviderRoute("coinbase", "v1", 2, "SECONDARY", True, True, ("1h",), ("spot",)),
        )
    )
    with pytest.raises(MarketDataVerificationError) as error:
        await MarketDataIngestor(
            [kraken, coinbase],
            configuration=config,
            cross_validation_tolerance=Decimal("0.01"),
        ).candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
            now=NOW,
        )
    assert error.value.quality is DataQuality.CONFLICTED


@pytest.mark.asyncio
async def test_emergency_route_is_not_selected_for_unsupported_timeframe() -> None:
    emergency = StubProvider("coingecko", [candle("coingecko")])
    config = StaticProviderConfiguration(
        (
            ProviderRoute("coingecko", "v1", 3, "EMERGENCY", True, False, ("1h", "4h"), ("spot",)),
        )
    )
    with pytest.raises(RuntimeError, match="No active authoritative"):
        await MarketDataIngestor([emergency], configuration=config).candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="15m")
        )


@pytest.mark.asyncio
async def test_historical_candles_may_be_old_when_latest_completed_candle_is_fresh() -> None:
    candles = []
    for hours_ago in (3, 2, 1, 0):
        close_time = NOW - timedelta(hours=hours_ago)
        candles.append(
            candle("kraken").model_copy(
                update={
                    "open_time": close_time - timedelta(hours=1),
                    "close_time": close_time,
                    "observed_at": close_time,
                    "received_at": close_time,
                }
            )
        )
    config = StaticProviderConfiguration(
        (ProviderRoute("kraken", "v1", 1, "PRIMARY", True, False, ("1h",), ("spot",)),)
    )
    result = await MarketDataIngestor(
        [StubProvider("kraken", candles)],
        configuration=config,
        freshness_seconds=120,
    ).candles(
        MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
        now=NOW,
    )
    assert len(result) == 4
    assert all(item.quality is DataQuality.VERIFIED for item in result)


@pytest.mark.asyncio
async def test_stale_latest_completed_candle_still_fails_closed() -> None:
    stale_close = NOW - timedelta(hours=3)
    stale = candle("kraken").model_copy(
        update={
            "open_time": stale_close - timedelta(hours=1),
            "close_time": stale_close,
            "observed_at": stale_close,
            "received_at": stale_close,
        }
    )
    config = StaticProviderConfiguration(
        (ProviderRoute("kraken", "v1", 1, "PRIMARY", True, False, ("1h",), ("spot",)),)
    )
    with pytest.raises(RuntimeError, match=r"kraken \[STALE\]: candle exceeds freshness limit"):
        await MarketDataIngestor(
            [StubProvider("kraken", [stale])],
            configuration=config,
            freshness_seconds=120,
        ).candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
            now=NOW,
        )
