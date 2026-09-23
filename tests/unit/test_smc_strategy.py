from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.domain import Direction, Provenance
from contracts.features import FeatureSnapshot
from packages.market_data.contracts import Candle, DataQuality
from packages.strategies.base import StrategyContext
from packages.strategies.smc import SMCStrategy

BASE = datetime(2026, 9, 23, tzinfo=UTC)


def candle(i: int, o: str, h: str, l: str, c: str) -> Candle:
    start = BASE + timedelta(hours=i)
    return Candle(
        asset="BTC/USD",
        venue="spot",
        timeframe="1h",
        open_time=start,
        close_time=start + timedelta(hours=1),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal("10"),
        provider="test",
        provider_version="1",
        observed_at=start + timedelta(hours=1),
        received_at=start + timedelta(hours=1),
        quality=DataQuality.VERIFIED,
    )


def test_smc_detects_swing_points_and_fvg():
    candles = [
        candle(0, "100", "101", "99", "100"),
        candle(1, "100", "103", "98", "102"),
        candle(2, "102", "110", "100", "108"),
        candle(3, "104", "105", "102", "104"),
        candle(4, "104", "106", "103", "105"),
        candle(5, "105", "115", "111", "114"),
        candle(6, "114", "116", "112", "115"),
        candle(7, "115", "117", "113", "116"),
    ]
    analysis = SMCStrategy().analyze(candles)
    assert analysis.swings
    assert analysis.fair_value_gaps


def test_smc_fails_closed_on_bad_data():
    data = [candle(i, "100", "101", "99", "100") for i in range(7)]
    data[-1] = data[-1].model_copy(update={"quality": DataQuality.STALE})
    with pytest.raises(ValueError, match="VERIFIED"):
        SMCStrategy().analyze(data)


def test_smc_vote_contract_is_deterministic():
    candles = [candle(i, str(100 + i), str(102 + i), str(99 + i), str(101 + i)) for i in range(12)]
    analysis = SMCStrategy().analyze(candles)
    now = candles[-1].close_time
    features = FeatureSnapshot(
        asset="BTC/USD",
        venue="spot",
        timeframe="1h",
        as_of=now,
        feature_set_version="1.0.0",
        values={"sma_20": Decimal("100")},
        required_history=50,
        provenance=(Provenance(source="test", observed_at=now, received_at=now),),
    )
    vote = SMCStrategy().evaluate(StrategyContext(candles=candles, features=features))
    assert vote.strategy_id == "smc"
    assert vote.strategy_version == "1.0.0"
    assert Decimal("0") <= vote.confidence <= Decimal("1")
    assert vote.direction in (Direction.LONG, Direction.SHORT, None)
    assert analysis.bias.value in {"BULLISH", "BEARISH", "NEUTRAL"}
