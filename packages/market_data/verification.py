from datetime import UTC, datetime, timedelta

from .contracts import Candle, DataQuality


class MarketDataVerificationError(ValueError):
    """Raised when market data cannot safely enter the verified pipeline."""


def verify_candle(
    candle: Candle,
    *,
    now: datetime,
    interval: timedelta,
    max_age_seconds: int,
) -> Candle:
    if not candle.asset.strip():
        raise MarketDataVerificationError("asset must be non-empty")
    if not candle.venue.strip():
        raise MarketDataVerificationError("venue must be non-empty")
    for timestamp_name in ("open_time", "close_time", "observed_at", "received_at"):
        if getattr(candle, timestamp_name).tzinfo is None:
            raise MarketDataVerificationError(f"{timestamp_name} must be timezone-aware")
    if candle.close_time <= candle.open_time:
        raise MarketDataVerificationError("close_time must be after open_time")
    if candle.close_time - candle.open_time != interval:
        raise MarketDataVerificationError("candle duration does not match timeframe")
    if candle.received_at < candle.observed_at:
        raise MarketDataVerificationError("received_at cannot precede observed_at")
    if min(candle.open, candle.high, candle.low, candle.close) <= 0:
        raise MarketDataVerificationError("OHLC prices must be positive")
    if candle.high < max(candle.open, candle.close):
        raise MarketDataVerificationError("high is below open/close")
    if candle.low > min(candle.open, candle.close):
        raise MarketDataVerificationError("low is above open/close")
    if candle.high < candle.low:
        raise MarketDataVerificationError("high cannot be below low")
    if candle.volume is not None and candle.volume < 0:
        raise MarketDataVerificationError("volume cannot be negative")

    age = (now.astimezone(UTC) - candle.close_time.astimezone(UTC)).total_seconds()
    if age < 0:
        raise MarketDataVerificationError("future candle is not admissible")
    if age > max_age_seconds:
        raise MarketDataVerificationError("candle is stale")
    return candle.model_copy(update={"quality": DataQuality.VERIFIED})


def verify_series(
    candles: list[Candle],
    *,
    now: datetime,
    interval: timedelta,
    max_age_seconds: int,
) -> list[Candle]:
    if not candles:
        raise MarketDataVerificationError("provider returned no candles")

    verified = [
        verify_candle(
            candle,
            now=now,
            interval=interval,
            max_age_seconds=max_age_seconds,
        )
        for candle in sorted(candles, key=lambda item: item.open_time)
    ]

    deduped: list[Candle] = []
    seen: set[tuple[str, str, str, object]] = set()
    for candle in verified:
        key = (candle.asset, candle.venue, candle.timeframe, candle.open_time)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candle)
    return deduped
