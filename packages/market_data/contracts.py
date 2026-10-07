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


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str
    instrument_type: str
    quote_currency: str | None = None
    contract_size: Decimal | None = None
    active: bool = True


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str = ""
    timeframe: str
    sequence: int | None = Field(default=None, ge=0)
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
    symbol: str = ""
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


class Trade(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str
    trade_id: str
    price: Decimal
    quantity: Decimal
    side: str | None = None
    event_time: datetime
    received_at: datetime
    provider: str
    provider_version: str | None = None
    request_id: UUID | None = None
    checksum: str | None = None
    quality: DataQuality = DataQuality.VERIFIED


class OrderBookLevel(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: Decimal
    quantity: Decimal


class OrderBook(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    event_time: datetime
    received_at: datetime
    provider: str
    provider_version: str | None = None
    sequence: int | None = Field(default=None, ge=0)
    request_id: UUID | None = None
    checksum: str | None = None
    quality: DataQuality = DataQuality.VERIFIED


class Funding(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str
    rate: Decimal
    funding_time: datetime
    received_at: datetime
    provider: str
    provider_version: str | None = None
    request_id: UUID | None = None
    checksum: str | None = None
    quality: DataQuality = DataQuality.VERIFIED


class OpenInterest(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str
    open_interest: Decimal
    event_time: datetime
    received_at: datetime
    provider: str
    provider_version: str | None = None
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


class ObservationManifestEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    venue: str
    symbol: str
    timeframe: str
    sequence: int | None
    open_time: datetime
    close_time: datetime
    provider: str
    provider_version: str | None
    observed_at: datetime
    received_at: datetime
    request_id: UUID | None
    checksum: str


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: UUID
    asset: str
    venue: str
    symbol: str
    timeframe: str
    provider: str
    provider_version: str | None
    request_id: UUID | None
    observation_checksum: str
    batch_checksum: str | None
    data_quality: DataQuality
    observed_at: datetime
    received_at: datetime
