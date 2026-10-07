from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class MarketStructureKind(StrEnum):
    TREND = "TREND"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class LiquidityKind(StrEnum):
    EQH = "EQH"
    EQL = "EQL"
    PDH = "PDH"
    PDL = "PDL"
    SESSION_HIGH = "SESSION_HIGH"
    SESSION_LOW = "SESSION_LOW"
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"


class ContextKind(StrEnum):
    PREMIUM = "PREMIUM"
    DISCOUNT = "DISCOUNT"
    EQUILIBRIUM = "EQUILIBRIUM"
    NEUTRAL = "NEUTRAL"


class QuantitativeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    return_1: Decimal
    return_window: Decimal
    atr: Decimal
    realized_volatility: Decimal
    momentum: Decimal
    volume_mean: Decimal
    volume_ratio: Decimal
    return_skew: Decimal
    return_kurtosis_excess: Decimal
    autocorrelation_1: Decimal
    correlation: Decimal | None = None


class MarketStructureSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: MarketStructureKind
    bias: str
    swing_highs: tuple[Decimal, ...]
    swing_lows: tuple[Decimal, ...]
    bos: tuple[str, ...]
    choch: tuple[str, ...]
    trend_strength: Decimal = Field(ge=0, le=1)
    range_high: Decimal | None = None
    range_low: Decimal | None = None


class LiquiditySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    levels: tuple[tuple[LiquidityKind, Decimal], ...]
    sweeps: tuple[str, ...]
    pools: tuple[Decimal, ...]
    session: str = "GLOBAL"


class SMCContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    fvg: tuple[tuple[str, Decimal, Decimal], ...]
    order_blocks: tuple[tuple[str, Decimal, Decimal], ...]
    premium_discount: ContextKind
    displacement: bool
    mitigation: tuple[str, ...]


class CRTSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: str
    reference_high: Decimal
    reference_low: Decimal
    swept: bool
    confirmation_index: int | None
    target: Decimal | None
    score: Decimal = Field(ge=0, le=1)
    reasons: tuple[str, ...] = ()


class IntelligenceContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    session: str
    news_active: bool = False
    external_bias: str | None = None
    notes: tuple[str, ...] = ()


class IntelligenceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    asset: str
    venue: str
    symbol: str
    timeframe: str
    as_of: datetime
    observation_window: tuple[datetime, datetime]
    engine_version: str
    configuration_version: str
    input_checksums: tuple[str, ...]
    quantitative: QuantitativeMetrics
    structure: MarketStructureSnapshot
    liquidity: LiquiditySnapshot
    smc: SMCContextSnapshot
    crt: CRTSnapshot
    regime: object
    context: IntelligenceContext
    snapshot_checksum: str
