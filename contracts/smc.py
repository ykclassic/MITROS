from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

class StructureKind(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"

class StructureBreakKind(StrEnum):
    BOS = "BOS"
    CHOCH = "CHOCH"

class DirectionBias(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class SwingPoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: StructureKind
    index: int = Field(ge=0)
    price: Decimal = Field(gt=0)
    occurred_at: datetime
    strength: int = Field(ge=1)

class StructureEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: StructureBreakKind
    direction: DirectionBias
    broken_price: Decimal = Field(gt=0)
    swing_index: int = Field(ge=0)
    confirmation_index: int = Field(ge=0)

class LiquiditySweep(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: DirectionBias
    level: Decimal = Field(gt=0)
    candle_index: int = Field(ge=0)
    reclaimed: bool

class FairValueGap(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: DirectionBias
    lower: Decimal = Field(gt=0)
    upper: Decimal = Field(gt=0)
    candle_index: int = Field(ge=2)

class OrderBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: DirectionBias
    lower: Decimal = Field(gt=0)
    upper: Decimal = Field(gt=0)
    candle_index: int = Field(ge=0)

class SMCAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)
    bias: DirectionBias
    swings: tuple[SwingPoint, ...]
    structure_events: tuple[StructureEvent, ...]
    liquidity_sweeps: tuple[LiquiditySweep, ...]
    fair_value_gaps: tuple[FairValueGap, ...]
    order_blocks: tuple[OrderBlock, ...]
    reasons: tuple[str, ...]
