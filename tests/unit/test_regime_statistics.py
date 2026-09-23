from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.regime import MarketRegime
from packages.intelligence.regime import RegimeDetector
from packages.intelligence.statistics import StatisticalEngine
from packages.market_data.contracts import Candle, DataQuality


def make_candle(i: int, close: str) -> Candle:
    t = datetime(2026, 9, 1, tzinfo=UTC) + timedelta(hours=i)
    price = Decimal(close)
    return Candle(
        asset="BTC/USD", venue="spot", timeframe="1h",
        open_time=t, close_time=t + timedelta(hours=1),
        open=price, high=price + 1, low=price - 1, close=price,
        volume=Decimal("10"), provider="test", observed_at=t, received_at=t,
        quality=DataQuality.VERIFIED,
    )


def candles(values: list[str]) -> list[Candle]:
    return [make_candle(i, value) for i, value in enumerate(values)]


def test_regime_detects_uptrend():
    result = RegimeDetector(minimum_sample=5, trend_threshold=Decimal("0.01")).classify(
        candles(["100", "101", "102", "103", "104"])
    )
    assert result.regime is MarketRegime.TREND_UP
    assert result.confidence > 0


def test_regime_fails_closed_on_stale_data():
    data = candles(["100", "101", "102", "103", "104"])
    data[-1] = data[-1].model_copy(update={"quality": DataQuality.STALE})
    with pytest.raises(ValueError, match="VERIFIED"):
        RegimeDetector(minimum_sample=5).classify(data)


def test_statistics_are_deterministic():
    result = StatisticalEngine(minimum_sample=5).analyze(candles(["100", "101", "100", "102", "101"]))
    assert result.sample_size == 4
    assert result.win_rate == Decimal("0.5")
    assert result.volatility >= 0
    assert -1 <= result.autocorrelation_1 <= 1


def test_statistics_reject_mixed_context():
    data = candles(["100", "101", "102", "103", "104"])
    data[-1] = data[-1].model_copy(update={"asset": "ETH/USD"})
    with pytest.raises(ValueError, match="asset"):
        StatisticalEngine(minimum_sample=5).analyze(data)
