from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.features import FeatureSnapshot
from packages.features.engine import FeatureEngine
from packages.features.indicators import atr, bollinger, ema, rsi, sma
from packages.market_data.contracts import Candle, DataQuality

BASE = datetime(2026, 9, 23, 20, tzinfo=UTC)

def candles(count: int = 60, *, quality: DataQuality = DataQuality.VERIFIED) -> list[Candle]:
    result = []
    for index in range(count):
        open_time = BASE + timedelta(hours=index)
        close = Decimal(100 + index)
        result.append(Candle(
            asset="BTC/USD",
            venue="spot",
            timeframe="1h",
            open_time=open_time,
            close_time=open_time + timedelta(hours=1),
            open=close - Decimal("0.5"),
            high=close + Decimal("1"),
            low=close - Decimal("1"),
            close=close,
            volume=Decimal("10"),
            provider="test",
            provider_version="1",
            observed_at=open_time + timedelta(hours=1),
            received_at=open_time + timedelta(hours=1),
            quality=quality,
        ))
    return result

def test_sma_ema_are_deterministic():
    values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
    assert sma(values, 3) == Decimal("3")
    assert ema(values, 3) == Decimal("3.25")

def test_rsi_is_bounded_and_atr_is_positive():
    data = candles()
    closes = [c.close for c in data]
    high = [c.high for c in data]
    low = [c.low for c in data]
    assert Decimal("0") <= rsi(closes, 14) <= Decimal("100")
    assert atr(high, low, closes, 14) > Decimal("0")

def test_bollinger_bands_are_ordered():
    values = [Decimal(100 + i) for i in range(20)]
    middle, upper, lower = bollinger(values, 20)
    assert lower <= middle <= upper

def test_feature_engine_emits_canonical_snapshot():
    snapshot = FeatureEngine().snapshot(candles())
    assert isinstance(snapshot, FeatureSnapshot)
    assert snapshot.feature_set_version == "1.0.0"
    assert set(snapshot.values) == {
        "return_1", "sma_20", "ema_20", "ema_50",
        "rsi_14", "macd_12_26", "macd_signal_9", "macd_histogram_12_26_9",
        "atr_14", "bb_mid_20", "bb_upper_20", "bb_lower_20", "bb_width_20",
    }
    assert all(value.is_finite() for value in snapshot.values.values())

def test_feature_engine_fails_closed_on_insufficient_history():
    with pytest.raises(ValueError, match="At least 50"):
        FeatureEngine().compute(candles(49))

def test_feature_engine_rejects_unverified_candles():
    with pytest.raises(ValueError, match="VERIFIED"):
        FeatureEngine().compute(candles(60, quality=DataQuality.STALE))

def test_feature_engine_rejects_duplicate_timestamps():
    data = candles()
    data[-1] = data[-2]
    with pytest.raises(ValueError, match="Duplicate"):
        FeatureEngine().compute(data)

def test_feature_engine_rejects_mixed_series():
    data = candles()
    data[-1] = data[-1].model_copy(update={"asset": "ETH/USD"})
    with pytest.raises(ValueError, match="asset"):
        FeatureEngine().compute(data)
