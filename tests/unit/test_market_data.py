from datetime import UTC,datetime,timedelta
from decimal import Decimal
import pytest
from packages.market_data.completeness import filter_completed_candles,validate_ohlcv
from packages.market_data.contracts import Candle,DataQuality
from packages.market_data.freshness import assess_freshness
from packages.market_data.router import ProviderRouter
from packages.market_data.symbols import SymbolMapper

NOW=datetime(2026,9,23,21,0,tzinfo=UTC)

def candle(close_minute=0)->Candle:
    opened=NOW-timedelta(hours=1,minutes=close_minute)
    return Candle(asset="BTC/USD",venue="test",timeframe="1h",open_time=opened-timedelta(hours=1),close_time=opened,
        open=Decimal("100"),high=Decimal("110"),low=Decimal("90"),close=Decimal("105"),
        provider="test",observed_at=opened,received_at=NOW)

def test_stale_candle_is_marked_stale():
    assert assess_freshness(candle(5),60,NOW).quality==DataQuality.STALE

def test_completed_filter():
    assert len(filter_completed_candles([candle()],NOW,timedelta(hours=1)))==1

def test_invalid_ohlc_rejected():
    bad=candle().model_copy(update={"high":Decimal("80")})
    with pytest.raises(ValueError): validate_ohlcv(bad)

def test_symbol_mapping_is_explicit():
    mapper=SymbolMapper({"finnhub":{"BTC/USD":"BINANCE:BTCUSDT"}})
    assert mapper.resolve("finnhub","BTC/USD").provider_symbol=="BINANCE:BTCUSDT"

def test_missing_symbol_mapping_fails_closed():
    mapper=SymbolMapper({"finnhub":{}})
    with pytest.raises(ValueError): mapper.resolve("finnhub","ETH/USD")

class FakeProvider:
    id="primary"; version="1"
    async def quote(self,request): raise RuntimeError("primary unavailable")
    async def candles(self,request): raise RuntimeError("primary unavailable")
    async def health(self): raise RuntimeError("primary unavailable")
class GoodProvider:
    id="secondary"; version="1"
    async def quote(self,request):
        from packages.market_data.contracts import Quote
        return Quote(asset=request.asset,venue=request.venue,last=Decimal("100"),provider=self.id,observed_at=NOW,received_at=NOW)
    async def candles(self,request): return []
    async def health(self):
        from packages.market_data.contracts import ProviderHealth
        return ProviderHealth(provider=self.id,available=True,checked_at=NOW)

@pytest.mark.asyncio
async def test_router_fails_over_to_secondary_provider():
    result=await ProviderRouter([FakeProvider(),GoodProvider()]).quote(__import__("packages.market_data.contracts",fromlist=["MarketDataRequest"]).MarketDataRequest(asset="BTC/USD",venue="spot"))
    assert result.provider=="secondary"
