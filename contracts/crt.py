from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CRTDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class CRTRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    candle_index: int = Field(ge=0)
    high: Decimal
    low: Decimal

    @property
    def size(self) -> Decimal:
        return self.high - self.low


class CRTSweep(BaseModel):
    model_config = ConfigDict(frozen=True)

    direction: CRTDirection
    reference_index: int = Field(ge=0)
    confirmation_index: int = Field(ge=0)
    swept_price: Decimal
    reclaim_price: Decimal
    target_price: Decimal


class CRTAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    direction: CRTDirection
    reference_range: CRTRange
    sweep: CRTSweep | None = None
    reasons: tuple[str, ...] = ()
