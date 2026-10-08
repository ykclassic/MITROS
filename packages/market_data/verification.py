from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from itertools import pairwise

from .checksum import canonical_checksum
from .contracts import Candle, DataQuality, ObservationManifestEntry
from .quality import DataQualityStateMachine


class MarketDataVerificationError(ValueError):
    """Raised when market data cannot safely enter the verified pipeline."""

    def __init__(self, message: str, *, quality: DataQuality = DataQuality.INVALID) -> None:
        super().__init__(message)
        self.quality = quality


def _observation_payload(candle: Candle) -> dict[str, Any]:
    return {
        "asset": candle.asset,
        "venue": candle.venue,
        "symbol": candle.symbol,
        "timeframe": candle.timeframe,
        "sequence": candle.sequence,
        "open_time": candle.open_time.isoformat(),
        "close_time": candle.close_time.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "provider": candle.provider,
        "provider_version": candle.provider_version,
        "observed_at": candle.observed_at.isoformat(),
        "received_at": candle.received_at.isoformat(),
        "request_id": str(candle.request_id) if candle.request_id else None,
    }


def observation_checksum(candle: Candle) -> str:
    return canonical_checksum(_observation_payload(candle))


def _raise_assessment(quality: DataQuality, reason: str) -> None:
    raise MarketDataVerificationError(reason, quality=quality)


def verify_candle(
    candle: Candle,
    *,
    now: datetime,
    interval: timedelta,
    max_age_seconds: int,
) -> Candle:
    if not candle.asset.strip() or not candle.venue.strip():
        _raise_assessment(DataQuality.INVALID, "asset and venue must be non-empty")
    if not candle.symbol.strip():
        candle = candle.model_copy(update={"symbol": candle.asset})
    for timestamp_name in ("open_time", "close_time", "observed_at", "received_at"):
        if getattr(candle, timestamp_name).tzinfo is None:
            _raise_assessment(DataQuality.INVALID, f"{timestamp_name} must be timezone-aware")

    assessment = DataQualityStateMachine.assess_candle(
        candle, now=now, interval=interval, max_age_seconds=max_age_seconds
    )
    if assessment.quality is not DataQuality.VERIFIED:
        _raise_assessment(assessment.quality, assessment.reasons[0])

    checksum = observation_checksum(candle)
    return candle.model_copy(update={"quality": DataQuality.VERIFIED, "checksum": checksum})


def _deduplicate(candles: list[Candle]) -> list[Candle]:
    deduped: list[Candle] = []
    seen: set[tuple[str, str, str, str, datetime]] = set()
    for candle in sorted(candles, key=lambda item: item.open_time):
        key = (candle.asset, candle.venue, candle.symbol, candle.timeframe, candle.open_time)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candle)
    return deduped


def _validate_continuity(candles: list[Candle], interval: timedelta) -> None:
    for previous, current in pairwise(candles):
        expected = previous.open_time + interval
        if current.open_time != expected:
            missing = int((current.open_time - expected).total_seconds() // interval.total_seconds())
            _raise_assessment(
                DataQuality.INCOMPLETE,
                f"dataset continuity gap: expected {expected.isoformat()}, "
                f"received {current.open_time.isoformat()} ({max(missing, 1)} missing interval(s))",
            )


def verify_series(
    candles: list[Candle],
    *,
    now: datetime,
    interval: timedelta,
    max_age_seconds: int,
) -> list[Candle]:
    if not candles:
        _raise_assessment(DataQuality.UNAVAILABLE, "provider returned no candles")
    stamped = _deduplicate(candles)
    reference = now.astimezone(UTC)
    closed = []
    for candle in stamped:
        if candle.open_time > reference:
            _raise_assessment(DataQuality.INVALID, "candle opens in the future")
        if candle.close_time <= reference:
            closed.append(candle)

    if not closed:
        _raise_assessment(
            DataQuality.UNAVAILABLE,
            "provider returned no completed candles",
        )

    verified = [
        verify_candle(
            candle,
            now=reference,
            interval=interval,
            max_age_seconds=max_age_seconds,
        )
        for candle in closed
    ]
    _validate_continuity(verified, interval)
    return verified


def build_manifest(candles: list[Candle]) -> tuple[ObservationManifestEntry, ...]:
    return tuple(
        ObservationManifestEntry(
            asset=candle.asset,
            venue=candle.venue,
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            sequence=candle.sequence,
            open_time=candle.open_time,
            close_time=candle.close_time,
            provider=candle.provider,
            provider_version=candle.provider_version,
            observed_at=candle.observed_at,
            received_at=candle.received_at,
            request_id=candle.request_id,
            checksum=candle.checksum or observation_checksum(candle),
        )
        for candle in candles
    )


def compare_series(
    primary: list[Candle],
    secondary: list[Candle],
    *,
    price_tolerance: Decimal = Decimal("0"),
) -> None:
    secondary_by_time = {item.open_time: item for item in secondary}
    for item in primary:
        other = secondary_by_time.get(item.open_time)
        if other is None:
            continue
        for field in ("open", "high", "low", "close"):
            left = getattr(item, field)
            right = getattr(other, field)
            scale = max(abs(left), abs(right), Decimal("1"))
            if abs(left - right) / scale > price_tolerance:
                _raise_assessment(
                    DataQuality.CONFLICTED,
                    f"provider conflict at {item.open_time.isoformat()}: {field} differs",
                )
