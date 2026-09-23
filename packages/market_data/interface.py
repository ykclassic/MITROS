from abc import ABC,abstractmethod
from .contracts import Candle,MarketDataRequest,ProviderHealth,Quote

class MarketDataProvider(ABC):
    id:str
    version:str
    @abstractmethod
    async def candles(self,request:MarketDataRequest)->list[Candle]: raise NotImplementedError
    @abstractmethod
    async def quote(self,request:MarketDataRequest)->Quote: raise NotImplementedError
    @abstractmethod
    async def health(self)->ProviderHealth: raise NotImplementedError
