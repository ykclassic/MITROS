from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.market_data.contracts import Candle, DataQuality, MarketDataRequest
from packages.market_data.guards import DownstreamDataGateError, require_verified
from packages.market_data.ingestion import MarketDataIngestor
from packages.market_data.routing import ProviderRoute, StaticProviderConfiguration
from packages.market_data.verification import MarketDataVerificationError, verify_series


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def candle(*, provider: str, close: Decimal = Decimal("105")) -> Candle:
    return Candle(
        asset="BTC/USD",
        venue="spot",
        symbol="BTC/USD",
        timeframe="1h",
        open_time=NOW - timedelta(hours=1),
        close_time=NOW,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=close,
        provider=provider,
        provider_version="1",
        observed_at=NOW,
        received_at=NOW,
    )


class Provider:
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
async def test_conflicting_authoritative_providers_fail_closed() -> None:
    primary = Provider("primary", [candle(provider="primary")])
    secondary = Provider("secondary", [candle(provider="secondary", close=Decimal("106"))])
    config = StaticProviderConfiguration(
        (
            ProviderRoute("primary", "1", 1, "PRIMARY", True, True, ("1h",), ("spot",)),
            ProviderRoute("secondary", "1", 2, "SECONDARY", True, True, ("1h",), ("spot",)),
        )
    )
    with pytest.raises(MarketDataVerificationError) as error:
        await MarketDataIngestor([primary, secondary], configuration=config).candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
            now=NOW,
        )
    assert error.value.quality is DataQuality.CONFLICTED


@pytest.mark.asyncio
async def test_unverified_data_cannot_enter_downstream_pipeline() -> None:
    invalid = candle(provider="primary").model_copy(update={"quality": DataQuality.DEGRADED})
    with pytest.raises(DownstreamDataGateError):
        require_verified([invalid])


def test_missing_data_blocks_downstream_pipeline() -> None:
    with pytest.raises(DownstreamDataGateError):
        require_verified([])


def test_gap_is_rejected_before_downstream_processing() -> None:
    first = candle(provider="primary").model_copy(
        update={
            "open_time": NOW - timedelta(hours=3),
            "close_time": NOW - timedelta(hours=2),
        }
    )
    second = candle(provider="primary")
    with pytest.raises(MarketDataVerificationError) as error:
        verify_series(
            [first, second],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=7200,
        )
    assert error.value.quality is DataQuality.INCOMPLETE
