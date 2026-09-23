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
        observed=datetime.fromisoformat(str(meta.get("last_refresh",values[0]["datetime"])))
        return [Candle(asset=request.asset,venue=request.venue,timeframe=request.timeframe or "1h",
            open_time=datetime.fromisoformat(str(x["datetime"]).replace("Z","+00:00")),
            close_time=datetime.fromisoformat(str(x["datetime"]).replace("Z","+00:00")),
            open=Decimal(x["open"]),high=Decimal(x["high"]),low=Decimal(x["low"]),close=Decimal(x["close"]),
            volume=Decimal(x["volume"]) if x.get("volume") else None,provider=self.id,provider_version=self.version,
            observed_at=observed,received_at=datetime.now(UTC)) for x in values]
    async def quote(self,request:MarketDataRequest)->Quote:
        m=self.symbols.resolve(self.id,request.asset); d=await self._get("/quote",{"symbol":m.provider_symbol,"apikey":self.api_key})
        observed=datetime.fromisoformat(str(d["datetime"])) if d.get("datetime") else datetime.now(UTC)
        return Quote(asset=request.asset,venue=request.venue,last=Decimal(str(d["close"])),provider=self.id,provider_version=self.version,observed_at=observed,received_at=datetime.now(UTC))
    async def health(self)->ProviderHealth:
        try: await self._get("/quote",{"symbol":"BTC/USD","apikey":self.api_key}); return ProviderHealth(provider=self.id,available=True,checked_at=datetime.now(UTC))
        except Exception as exc: return ProviderHealth(provider=self.id,available=False,checked_at=datetime.now(UTC),error=str(exc))

class FinnhubProvider(HTTPProviderBase):
    id="finnhub"; version="v1"
    def __init__(self,*,api_key:str,symbols:SymbolMapper,client:httpx.AsyncClient|None=None)->None:
        super().__init__(api_key=api_key,base_url="https://finnhub.io/api",client=client); self.symbols=symbols
    async def candles(self,request:MarketDataRequest)->list[Candle]:
        m=self.symbols.resolve(self.id,request.asset)
        resolution={"1m":"1","5m":"5","15m":"15","30m":"30","1h":"60","4h":"240","1d":"D"}.get(request.timeframe or "1h")
        if resolution is None: raise ValueError(f"Unsupported Finnhub timeframe: {request.timeframe}")
        import time
        end=int(time.time()); start=end-(request.limit*3600 if resolution=="60" else request.limit*86400)
        data=await self._get("/v1/stock/candle",{"symbol":m.provider_symbol,"resolution":resolution,"from":start,"to":end,"token":self.api_key})
        if data.get("s")!="ok": raise RuntimeError(f"Finnhub candle status: {data.get('s')}")
        observed=utc_from_epoch(int(data["t"][-1]))
        return [Candle(asset=request.asset,venue=request.venue,timeframe=request.timeframe or "1h",
            open_time=utc_from_epoch(int(ts)),close_time=utc_from_epoch(int(ts)),
            open=Decimal(str(o)),high=Decimal(str(h)),low=Decimal(str(l)),close=Decimal(str(c)),
            volume=Decimal(str(v)) if v is not None else None,provider=self.id,provider_version=self.version,
            observed_at=observed,received_at=datetime.now(UTC))
            for ts,o,h,l,c,v in zip(data["t"],data["o"],data["h"],data["l"],data["c"],data.get("v",[None]*len(data["t"]))) ]
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
        m=self.symbols.resolve(self.id,request.asset)
        interval=request.timeframe or "1h"
        if interval not in {"1m","5m","15m","30m","60min"}: raise ValueError(f"Unsupported Alpha Vantage timeframe: {interval}")
        function="CRYPTO_INTRADAY" if "/" in request.asset else "TIME_SERIES_INTRADAY"
        params={"function":function,"symbol":m.provider_symbol,"interval":"60min" if interval=="1h" else interval,"outputsize":"full","apikey":self.api_key}
        if function=="CRYPTO_INTRADAY": params["market"]="USD"
        data=await self._get("/query",params)
        key=next((k for k in data if k.startswith(("Time Series Crypto","Time Series ("))),None)
        if key is None: raise RuntimeError(f"Alpha Vantage returned no time-series payload: {data.get('Note') or data.get('Error Message')}")
        rows=data[key]
        items=list(rows.items())[:request.limit]
        observed=datetime.fromisoformat(items[0][0].replace(" ","T")).replace(tzinfo=UTC)
        return [Candle(asset=request.asset,venue=request.venue,timeframe=request.timeframe or "1h",
            open_time=datetime.fromisoformat(ts.replace(" ","T")).replace(tzinfo=UTC),
            close_time=datetime.fromisoformat(ts.replace(" ","T")).replace(tzinfo=UTC),
            open=Decimal(str(row.get("1. open") or row.get("1a. open (USD)"))),
            high=Decimal(str(row.get("2. high") or row.get("2a. high (USD)"))),
            low=Decimal(str(row.get("3. low") or row.get("3a. low (USD)"))),
            close=Decimal(str(row.get("4. close") or row.get("4a. close (USD)"))),
            volume=Decimal(str(row.get("5. volume") or row.get("5. volume (USD)") or "0")),
            provider=self.id,provider_version=self.version,observed_at=observed,received_at=datetime.now(UTC))
            for ts,row in items]
    async def quote(self,request:MarketDataRequest)->Quote:
        m=self.symbols.resolve(self.id,request.asset); d=await self._get("/query",{"function":"GLOBAL_QUOTE","symbol":m.provider_symbol,"apikey":self.api_key})
        q=d.get("Global Quote",{}); observed=datetime.now(UTC)
        return Quote(asset=request.asset,venue=request.venue,last=Decimal(str(q["05. price"])),provider=self.id,provider_version=self.version,observed_at=observed,received_at=datetime.now(UTC))
    async def health(self)->ProviderHealth:
        try: await self.quote(MarketDataRequest(asset="BTC/USD",venue="spot")); return ProviderHealth(provider=self.id,available=True,checked_at=datetime.now(UTC))
        except Exception as exc: return ProviderHealth(provider=self.id,available=False,checked_at=datetime.now(UTC),error=str(exc))
