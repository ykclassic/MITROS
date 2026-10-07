from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class MarketRegime(StrEnum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT = "BREAKOUT"
    TRANSITION = "TRANSITION"
    NEWS = "NEWS"
    UNKNOWN = "UNKNOWN"


class RegimeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    regime: MarketRegime
    confidence: Decimal = Field(ge=0, le=1)
    trend_strength: Decimal = Field(ge=0, le=1)
    volatility: Decimal = Field(ge=0)
    sample_size: int = Field(ge=0)
    model_version: str = "deterministic-rules-2.0.0"
    observation_window: tuple[datetime, datetime] | None = None
    timestamp: datetime | None = None
    reasons: tuple[str, ...] = ()


class StatisticalSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    sample_size: int = Field(ge=0)
    mean_return: Decimal
    volatility: Decimal = Field(ge=0)
    win_rate: Decimal = Field(ge=0, le=1)
    downside_deviation: Decimal = Field(ge=0)
    autocorrelation_1: Decimal = Field(ge=-1, le=1)
    z_score: Decimal
    reasons: tuple[str, ...] = ()
