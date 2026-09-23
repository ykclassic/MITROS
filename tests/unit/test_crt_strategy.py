from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.crt import CRTDirection
from contracts.domain import Direction, Provenance
from contracts.features import FeatureSnapshot
from packages.market_data.contracts import Candle, DataQuality
from packages.strategies.base import StrategyContext
from packages.strategies.crt import CRTStrategy

BASE = datetime(2026, 9, 23, tzinfo=UTC)


def candle(i: int, o: str, h: str, l: str, c: str) -> Candle:
    start = BASE + timedelta(hours=i)
    return Candle(
        asset="BTC/USD", venue="spot", timeframe="1h",
        open_time=start, close_time=start + timedelta(hours=1),
        open=Decimal(o), high=Decimal(h), low=Decimal(l), close=Decimal(c),
        volume=Decimal("10"), provider="test", provider_version="1",
        observed_at=start + timedelta(hours=1), received_at=start + timedelta(hours=1),
        quality=DataQuality.VERIFIED,
    )


def features(now: datetime) -> FeatureSnapshot:
    return FeatureSnapshot(
        asset="BTC/USD", venue="spot", timeframe="1h", as_of=now,
        feature_set_version="1.0.0", values={"sma_20": Decimal("100")},
        required_history=50,
        provenance=(Provenance(source="test", observed_at=now, received_at=now),),
    )


def test_crt_bullish_sweep_reclaims_reference_low():
    candles = [candle(0, "100", "105", "95", "101"), candle(1, "101", "103", "93", "99")]
    analysis = CRTStrategy().analyze(candles)
    assert analysis.direction is CRTDirection.BULLISH
    assert analysis.sweep is not None
    assert analysis.sweep.target_price == Decimal("105")
    vote = CRTStrategy().evaluate(StrategyContext(candles=candles, features=features(candles[-1].close_time)))
    assert vote.direction is Direction.LONG
    assert vote.confidence == Decimal("1")


def test_crt_bearish_sweep_reclaims_reference_high():
    candles = [candle(0, "100", "105", "95", "101"), candle(1, "101", "108", "99", "104")]
    analysis = CRTStrategy().analyze(candles)
    assert analysis.direction is CRTDirection.BEARISH
    assert analysis.sweep is not None
    assert analysis.sweep.target_price == Decimal("95")
    vote = CRTStrategy().evaluate(StrategyContext(candles=candles, features=features(candles[-1].close_time)))
    assert vote.direction is Direction.SHORT


def test_crt_neutral_without_reclaim():
    candles = [candle(0, "100", "105", "95", "101"), candle(1, "101", "107", "94", "106")]
    analysis = CRTStrategy().analyze(candles)
    assert analysis.direction is CRTDirection.NEUTRAL
    assert analysis.sweep is None
    vote = CRTStrategy().evaluate(StrategyContext(candles=candles, features=features(candles[-1].close_time)))
    assert vote.direction is None
    assert vote.confidence == Decimal("0")


def test_crt_fails_closed_on_bad_data():
    candles = [
        candle(0, "100", "105", "95", "101"),
        candle(1, "101", "108", "99", "104").model_copy(update={"quality": DataQuality.STALE}),
    ]
    with pytest.raises(ValueError, match="VERIFIED"):
        CRTStrategy().analyze(candles)


def test_crt_rejects_mixed_context():
    candles = [
        candle(0, "100", "105", "95", "101"),
        candle(1, "101", "108", "99", "104").model_copy(update={"asset": "ETH/USD"}),
    ]
    with pytest.raises(ValueError, match="asset"):
        CRTStrategy().analyze(candles)
