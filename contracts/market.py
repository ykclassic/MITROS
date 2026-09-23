from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel,ConfigDict
from contracts.domain import Provenance
class MarketDataSnapshot(BaseModel):
    model_config=ConfigDict(frozen=True)
    asset:str; venue:str; timeframe:str; as_of:datetime; values:dict[str,Decimal]; provenance:tuple[Provenance,...]
