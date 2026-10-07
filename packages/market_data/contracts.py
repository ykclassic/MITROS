from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DataQuality(StrEnum):
    VERIFIED = "VERIFIED"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    CONFLICTED = "CONFLICTED"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    provider: str
    provider_version: str | None = None
    observed_at: datetime
    received_at: datetime
    request_id: UUID | None = None
    checksum: str | None = None
    quality: DataQuality = DataQuality.VERIFIED


class Quote(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal | None = None
    provider: str
    provider_version: str | None = None
    observed_at: datetime
    received_at: datetime
    request_id: UUID | None = None
    checksum: str | None = None
    quality: DataQuality = DataQuality.VERIFIED


class ProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    available: bool
    checked_at: datetime
    latency_ms: int | None = None
    error: str | None = None


class MarketDataRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    timeframe: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    provider_version: str | None = None
    observed_at: datetime
    received_at: datetime
    request_id: UUID
    payload: dict[str, object]
