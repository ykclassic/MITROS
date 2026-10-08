from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.market_data.contracts import Candle, DataQuality, MarketDataRequest
from packages.market_data.ingestion import MarketDataIngestor
from packages.market_data.verification import MarketDataVerificationError, verify_series


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def make_candle(
    offset_minutes: int = 0,
    *,
    open_time: datetime | None = None,
    close_time: datetime | None = None,
    close: Decimal = Decimal("105"),
) -> Candle:
    end = close_time or (NOW - timedelta(minutes=offset_minutes))
    return Candle(
        asset="BTC/USD",
        venue="spot",
        symbol="BTC/USD",
        timeframe="1h",
        sequence=None,
        open_time=open_time or end - timedelta(hours=1),
        close_time=end,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=close,
        provider="test",
        provider_version="1",
        observed_at=end,
        received_at=NOW,
    )


def test_future_closed_boundary_is_incomplete() -> None:
    with pytest.raises(MarketDataVerificationError) as error:
        verify_series(
            [make_candle(close_time=NOW + timedelta(minutes=1))],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=120,
        )
    assert error.value.quality is DataQuality.INCOMPLETE


def test_future_opening_candle_is_invalid() -> None:
    with pytest.raises(MarketDataVerificationError) as error:
        verify_series(
            [make_candle(
                open_time=NOW + timedelta(minutes=1),
                close_time=NOW + timedelta(hours=1, minutes=1),
            )],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=120,
        )
    assert error.value.quality is DataQuality.INVALID


def test_current_forming_candle_is_excluded_from_verified_series() -> None:
    closed = make_candle(close_time=NOW - timedelta(hours=1))
    forming = make_candle(
        open_time=NOW,
        close_time=NOW + timedelta(hours=1),
    )
    candles = verify_series(
        [closed, forming],
        now=NOW,
        interval=timedelta(hours=1),
        max_age_seconds=120,
    )
    assert len(candles) == 1
    assert candles[0].close_time == closed.close_time
    assert candles[0].quality is DataQuality.VERIFIED


def test_stale_candle_fails_closed() -> None:
    with pytest.raises(MarketDataVerificationError) as error:
        verify_series(
            [make_candle(63 * 60)],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=120,
        )
    assert error.value.quality is DataQuality.STALE


def test_duplicate_candles_are_deterministically_removed_and_checksummed() -> None:
    candles = verify_series(
        [make_candle(), make_candle()],
        now=NOW,
        interval=timedelta(hours=1),
        max_age_seconds=120,
    )
    assert len(candles) == 1
    assert candles[0].quality is DataQuality.VERIFIED
    assert candles[0].checksum


def test_dataset_gap_fails_closed() -> None:
    first = make_candle(close_time=NOW - timedelta(hours=2))
    second = make_candle(close_time=NOW)
    with pytest.raises(MarketDataVerificationError) as error:
        verify_series(
            [first, second],
            now=NOW,
            interval=timedelta(hours=1),
            max_age_seconds=7200,
        )
    assert error.value.quality is DataQuality.INCOMPLETE
    assert "continuity gap" in str(error.value)


def test_quality_state_machine_is_explicit() -> None:
    assert DataQuality.VERIFIED.value == "VERIFIED"
    assert DataQuality.INCOMPLETE.value == "INCOMPLETE"
    assert DataQuality.CONFLICTED.value == "CONFLICTED"


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
    primary = Provider([make_candle(63 * 60)])
    secondary = Provider([make_candle()])
    result = await MarketDataIngestor([primary, secondary]).candles(
        MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h"),
        now=NOW,
    )
    assert result[0].provider == "test"
    assert result[0].request_id is not None
