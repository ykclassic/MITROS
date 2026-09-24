from decimal import Decimal
import httpx
import pytest
from packages.market_data.providers import AlphaVantageProvider,FinnhubProvider,TwelveDataProvider
from packages.market_data.symbols import SymbolMapper
from packages.market_data.contracts import MarketDataRequest

class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self,payload): self.payload=payload
    async def handle_async_request(self,request):
        return httpx.Response(200,json=self.payload,request=request)

@pytest.mark.asyncio
async def test_twelve_data_parser_preserves_provider_timestamp():
    payload={"values":[{"datetime":"2026-09-23T20:00:00Z","open":"100","high":"110","low":"90","close":"105","volume":"10"}],"meta":{"last_refresh":"2026-09-23T20:00:00Z"}}
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        p=TwelveDataProvider(api_key="x",symbols=SymbolMapper({"twelvedata":{"BTC/USD":"BTC/USD"}}),client=client)
        c=(await p.candles(MarketDataRequest(asset="BTC/USD",venue="spot",timeframe="1h",limit=1)))[0]
    assert c.provider=="twelvedata" and c.observed_at.isoformat()=="2026-09-23T20:00:00+00:00" and c.close==Decimal("105")

@pytest.mark.asyncio
async def test_finnhub_parser_preserves_provider_timestamp():
    payload={"s":"ok","t":[1790193600],"o":[100],"h":[110],"l":[90],"c":[105],"v":[10]}
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        p=FinnhubProvider(api_key="x",symbols=SymbolMapper({"finnhub":{"BTC/USD":"BINANCE:BTCUSDT"}}),client=client)
        c=(await p.candles(MarketDataRequest(asset="BTC/USD",venue="spot",timeframe="1h",limit=1)))[0]
    assert c.provider=="finnhub" and c.close==Decimal("105")

@pytest.mark.asyncio
async def test_alpha_vantage_parser_preserves_provider_timestamp():
    payload={"Time Series Crypto (60min)":{"2026-09-23 20:00:00":{"1a. open (USD)":"100","2a. high (USD)":"110","3a. low (USD)":"90","4a. close (USD)":"105","5. volume":"10"}}}
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        p=AlphaVantageProvider(api_key="x",symbols=SymbolMapper({"alphavantage":{"BTC/USD":"BTC"}}),client=client)
        c=(await p.candles(MarketDataRequest(asset="BTC/USD",venue="spot",timeframe="1h",limit=1)))[0]
    assert c.provider=="alphavantage" and c.close==Decimal("105")


@pytest.mark.asyncio
async def test_alpha_vantage_crypto_quote_uses_realtime_exchange_rate():
    payload = {
        "Realtime Currency Exchange Rate": {
            "1. From_Currency Code": "BTC",
            "3. To_Currency Code": "USD",
            "5. Exchange Rate": "65000.12",
            "6. Last Refreshed": "2026-09-24 01:00:00",
        }
    }
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        p = AlphaVantageProvider(
            api_key="x",
            symbols=SymbolMapper({"alphavantage": {"BTC/USD": "BTC"}}),
            client=client,
        )
        q = await p.quote(MarketDataRequest(asset="BTC/USD", venue="spot"))
    assert q.provider == "alphavantage"
    assert q.last == Decimal("65000.12")
    assert q.observed_at.isoformat() == "2026-09-24T01:00:00+00:00"
