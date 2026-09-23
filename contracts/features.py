from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from contracts.domain import Provenance

class FeatureSnapshot(BaseModel):
    """Immutable, provenance-bearing feature vector for one completed candle."""
    model_config = ConfigDict(frozen=True)
    asset: str
    venue: str
    timeframe: str
    as_of: datetime
    feature_set_version: str
    values: dict[str, Decimal]
    required_history: int = Field(ge=1)
    provenance: tuple[Provenance, ...]
