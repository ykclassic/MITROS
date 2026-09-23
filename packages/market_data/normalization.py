from datetime import datetime
from decimal import Decimal
from .contracts import Candle,ProviderResponse

def normalize_candle(response:ProviderResponse,row:dict[str,object],*,asset:str,venue:str,timeframe:str)->Candle:
    return Candle(
        asset=asset,venue=venue,timeframe=timeframe,
        open_time=datetime.fromisoformat(str(row["open_time"])),
        close_time=datetime.fromisoformat(str(row["close_time"])),
        open=Decimal(str(row["open"])),high=Decimal(str(row["high"])),
        low=Decimal(str(row["low"])),close=Decimal(str(row["close"])),
        volume=Decimal(str(row["volume"])) if row.get("volume") is not None else None,
        provider=response.provider,provider_version=response.provider_version,
        observed_at=response.observed_at,received_at=response.observed_at,
    )
