from datetime import UTC,datetime
from decimal import Decimal
import httpx
from .contracts import Candle,MarketDataRequest,ProviderHealth,Quote
from .http import HTTPProviderBase,utc_from_epoch
from .symbols import SymbolMapper

class TwelveDataProvider(HTTPProviderBase):
    id="twelvedata"; version="v1"
    def __init__(self,*,api_key:str,symbols:SymbolMapper,client:httpx.AsyncClient|None=None)->None:
        super().__init__(api_key=api_key,base_url="https://api.twelvedata.com",client=client); self.symbols=symbols
    async def candles(self,request:MarketDataRequest)->list[Candle]:
        mapping=self.symbols.resolve(self.id,request.asset)
        data=await self._get("/time_series",{"symbol":mapping.provider_symbol,"interval":request.timeframe or "1h","outputsize":request.limit,"apikey":self.api_key})
        values=data.get("values",[])
        meta=data.get("meta",{})
        observed=datetime.fromisoformat(str(meta.get("last_refresh",values[0]["datetime"])).replace("Z","+00:00"))
        return [Candle(asset=request.asset,venue=request.venue,timeframe=request.timeframe or "1h",
            open_time=datetime.fromisoformat(str(x["datetime"]).replace("Z","+00:00")),
            close_time=datetime.fromisoformat(str(x["datetime"]).replace("Z","+00:00")),
            open=Decimal(x["open"]),high=Decimal(x["high"]),low=Decimal(x["low"]),close=Decimal(x["close"]),
            volume=Decimal(x["volume"]) if x.get("volume") else None,provider=self.id,provider_version=self.version,
            observed_at=observed,received_at=datetime.now(UTC)) for x in values]
    async def quote(self,request:MarketDataRequest)->Quote:
        m=self.symbols.resolve(self.id,request.asset); d=await self._get("/quote",{"symbol":m.provider_symbol,"apikey":self.api_key})
        observed=datetime.fromisoformat(str(d["datetime"]).replace("Z","+00:00")) if d.get("datetime") else datetime.now(UTC)
        return Quote(asset=request.asset,venue=request.venue,last=Decimal(str(d["close"])),provider=self.id,provider_version=self.version,observed_at=observed,received_at=datetime.now(UTC))
    async def health(self)->ProviderHealth:
        try: await self._get("/quote",{"symbol":"BTC/USD","apikey":self.api_key}); return ProviderHealth(provider=self.id,available=True,checked_at=datetime.now(UTC))
        except Exception as exc: return ProviderHealth(provider=self.id,available=False,checked_at=datetime.now(UTC),error=str(exc))

class FinnhubProvider(HTTPProviderBase):
    id="finnhub"; version="v1"
    def __init__(self,*,api_key:str,symbols:SymbolMapper,client:httpx.AsyncClient|None=None)->None:
        super().__init__(api_key=api_key,base_url="https://finnhub.io/api",client=client); self.symbols=symbols
    async def candles(self,request:MarketDataRequest)->list[Candle]:
        raise NotImplementedError("Finnhub candle interval aggregation is implemented in the ingestion worker")
    async def quote(self,request:MarketDataRequest)->Quote:
        m=self.symbols.resolve(self.id,request.asset); d=await self._get("/v1/quote",{"symbol":m.provider_symbol,"token":self.api_key})
        observed=utc_from_epoch(int(d["t"])) if d.get("t") else datetime.now(UTC)
        return Quote(asset=request.asset,venue=request.venue,last=Decimal(str(d["c"])),provider=self.id,provider_version=self.version,observed_at=observed,received_at=datetime.now(UTC))
    async def health(self)->ProviderHealth:
        try: await self.quote(MarketDataRequest(asset="BTC/USD",venue="spot")); return ProviderHealth(provider=self.id,available=True,checked_at=datetime.now(UTC))
        except Exception as exc: return ProviderHealth(provider=self.id,available=False,checked_at=datetime.now(UTC),error=str(exc))

class AlphaVantageProvider(HTTPProviderBase):
    id="alphavantage"; version="v1"
    def __init__(self,*,api_key:str,symbols:SymbolMapper,client:httpx.AsyncClient|None=None)->None:
        super().__init__(api_key=api_key,base_url="https://www.alphavantage.co",client=client); self.symbols=symbols
    async def candles(self,request:MarketDataRequest)->list[Candle]:
        raise NotImplementedError("Alpha Vantage interval mapping is implemented in the ingestion worker")
    async def quote(self,request:MarketDataRequest)->Quote:
        m=self.symbols.resolve(self.id,request.asset); d=await self._get("/query",{"function":"GLOBAL_QUOTE","symbol":m.provider_symbol,"apikey":self.api_key})
        q=d.get("Global Quote",{}); observed=datetime.now(UTC)
        return Quote(asset=request.asset,venue=request.venue,last=Decimal(str(q["05. price"])),provider=self.id,provider_version=self.version,observed_at=observed,received_at=datetime.now(UTC))
    async def health(self)->ProviderHealth:
        try: await self.quote(MarketDataRequest(asset="BTC/USD",venue="spot")); return ProviderHealth(provider=self.id,available=True,checked_at=datetime.now(UTC))
        except Exception as exc: return ProviderHealth(provider=self.id,available=False,checked_at=datetime.now(UTC),error=str(exc))
