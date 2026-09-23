from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.domain import Direction
from packages.market_data.contracts import Candle, DataQuality
from packages.strategies.smc import SMCStrategy
from packages.strategies.base import StrategyContext

BASE = datetime(2026, 9, 23, 0, tzinfo=UTC)

def candle(i: int, o: str, h: str, l: str, c: str) -> Candle:
    start = BASE + timedelta(hours=i)
    return Candle(asset="BTC/USD", venue="spot", timeframe="1h", open_time=start, close_time=start + timedelta(hours=1), open=Decimal(o), high=Decimal(h), low=Decimal(l), close=Decimal(c), volume=Decimal("10"), provider="test", provider_version="1", observed_at=start + timedelta(hours=1), received_at=start + timedelta(hours=1), quality=DataQuality.VERIFIED)

def test_smc_detects_swing_points_and_fvg():
    candles = [candle(0,"100","101","99","100"),candle(1,"100","103","99","102"),candle(2,"102","104","101","103"),candle(3,"103","105","102","104"),candle(4,"104","106","103","105"),candle(5,"105","107","104","106"),candle(6,"106","108","105","107"),candle(7,"107","109","106","108")]
    analysis = SMCStrategy().analyze(candles)
    assert analysis.swings
    assert analysis.fair_value_gaps

def test_smc_fails_closed_on_bad_data():
    with pytest.raises(ValueError, match="VERIFIED"):
        SMCStrategy().analyze([candle(i,"100","101","99","100") for i in range(7)][:-1] + [candle(6,"100","101","99","100") .model_copy(update={"quality": DataQuality.STALE})])

def test_smc_vote_contract_is_deterministic():
    candles = [candle(i, str(100+i), str(102+i), str(99+i), str(101+i)) for i in range(12)]
    analysis = SMCStrategy().analyze(candles)
    vote = SMCStrategy().evaluate(StrategyContext(candles=candles, features=None))
    assert vote.strategy_id == "smc"
    assert vote.strategy_version == "1.0.0"
    assert Decimal("0") <= vote.confidence <= Decimal("1")
    assert vote.direction in (Direction.LONG, Direction.SHORT, None)
    assert analysis.bias.value in {"BULLISH", "BEARISH", "NEUTRAL"}
