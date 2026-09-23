from decimal import Decimal
from pydantic import BaseModel,ConfigDict
from contracts.market import MarketDataSnapshot
class SignalContext(BaseModel):
    model_config=ConfigDict(frozen=True)
    market:MarketDataSnapshot
    features:dict[str,Decimal]
    regime:str
