from decimal import Decimal
from contracts.domain import MarketDataSnapshot
from pydantic import BaseModel,ConfigDict
class SignalContext(BaseModel):
    model_config=ConfigDict(frozen=True)
    market:MarketDataSnapshot
    features:dict[str,Decimal]
    regime:str
