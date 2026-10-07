from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.intelligence import IntelligenceContext
from contracts.regime import MarketRegime
from packages.intelligence import MarketIntelligenceEngine
from packages.intelligence.crt import analyze_crt
from packages.market_data.contracts import Candle, DataQuality
from packages.market_data.verification import observation_checksum

BASE = datetime(2026, 10, 1, tzinfo=UTC)


def candles(count: int = 30) -> list[Candle]:
    result: list[Candle] = []
    for i in range(count):
        start = BASE + timedelta(hours=i)
        close = Decimal("100") + Decimal(i) + (Decimal("0.5") if i % 3 == 0 else Decimal("0"))
        candle = Candle(
            asset="BTC/USD", venue="spot", symbol="BTC/USD", timeframe="1h",
            open_time=start, close_time=start + timedelta(hours=1),
            open=close - Decimal("0.5"), high=close + Decimal("1"),
            low=close - Decimal("1"), close=close, volume=Decimal("100"),
            provider="test", provider_version="1", observed_at=start + timedelta(hours=1),
            received_at=start + timedelta(hours=1), quality=DataQuality.VERIFIED,
        )
        result.append(candle.model_copy(update={"checksum": observation_checksum(candle)}))
    return result


def test_intelligence_snapshot_is_reproducible():
    data = candles()
    engine = MarketIntelligenceEngine()
    first = engine.snapshot(data)
    second = engine.snapshot(data)
    assert first == second
    assert first.snapshot_checksum == second.snapshot_checksum
    assert first.regime.confidence != Decimal("1") or first.regime.regime is not MarketRegime.UNKNOWN


def test_regime_confidence_is_not_trade_probability():
    snapshot = MarketIntelligenceEngine().snapshot(candles())
    assert hasattr(snapshot.regime, "confidence")
    assert not hasattr(snapshot.regime, "trade_probability")


def test_news_context_changes_regime_without_changing_probability_semantics():
    snapshot = MarketIntelligenceEngine().snapshot(
        candles(), context=IntelligenceContext(session="LONDON", news_active=True)
    )
    assert snapshot.regime.regime is MarketRegime.NEWS
    assert snapshot.regime.model_version == "deterministic-rules-2.0.0"


def test_crt_is_measurable():
    data = candles(3)
    reference = data[-2]
    confirmation = data[-1].model_copy(update={
        "high": reference.high + Decimal("2"),
        "close": reference.high - Decimal("0.1"),
    })
    result = analyze_crt([reference, confirmation])
    assert result.swept is True
    assert result.direction == "BEARISH"
    assert Decimal("0") <= result.score <= Decimal("1")


def test_intelligence_fails_closed_on_unchecksummed_data():
    data = candles()
    data[-1] = data[-1].model_copy(update={"checksum": None})
    with pytest.raises(ValueError, match="checksummed"):
        MarketIntelligenceEngine().snapshot(data)


def test_intelligence_fails_closed_on_unverified_data():
    data = candles()
    data[-1] = data[-1].model_copy(update={"quality": DataQuality.STALE})
    with pytest.raises(ValueError, match="VERIFIED"):
        MarketIntelligenceEngine().snapshot(data)
