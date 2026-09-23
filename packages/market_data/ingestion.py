from datetime import UTC,datetime,timedelta
from .contracts import Candle,MarketDataRequest
from .freshness import assess_freshness
from .interface import MarketDataProvider
from .completeness import filter_completed_candles,validate_ohlcv

class MarketDataIngestor:
    def __init__(self,providers:list[MarketDataProvider],freshness_seconds:int=120)->None:
        if not providers: raise ValueError("At least one market-data provider is required")
        self.providers=tuple(providers); self.freshness_seconds=freshness_seconds

    async def candles(self,request:MarketDataRequest,*,interval:timedelta,now:datetime|None=None)->list[Candle]:
        errors:list[str]=[]
        reference=now or datetime.now(UTC)
        for provider in self.providers:
            try:
                candles=await provider.candles(request)
                valid=[]
                for candle in candles:
                    validate_ohlcv(candle)
                    valid.append(assess_freshness(candle,self.freshness_seconds,reference))
                completed=filter_completed_candles(valid,reference,interval)
                if completed: return completed
                errors.append(f"{provider.id}: no completed candles")
            except Exception as exc: errors.append(f"{provider.id}: {exc}")
        raise RuntimeError("No authoritative completed market data available: "+" | ".join(errors))
