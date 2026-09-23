from datetime import datetime,timezone
from .contracts import Candle,DataQuality

def assess_freshness(candle:Candle,max_age_seconds:int,now:datetime|None=None)->Candle:
    reference=now or datetime.now(timezone.utc)
    age=(reference-candle.close_time).total_seconds()
    quality=DataQuality.VERIFIED if 0<=age<=max_age_seconds else DataQuality.STALE
    return candle.model_copy(update={"quality":quality})
