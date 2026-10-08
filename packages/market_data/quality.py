from dataclasses import dataclass
from typing import ClassVar
from datetime import UTC, datetime, timedelta

from .contracts import Candle, DataQuality


@dataclass(frozen=True)
class QualityAssessment:
    quality: DataQuality
    reasons: tuple[str, ...] = ()


class DataQualityStateMachine:
    """Deterministic, fail-closed quality classification."""

    _allowed: ClassVar[dict[DataQuality, frozenset[DataQuality]]] = {
        DataQuality.UNAVAILABLE: frozenset({DataQuality.UNAVAILABLE, DataQuality.DEGRADED}),
        DataQuality.DEGRADED: frozenset(
            {DataQuality.DEGRADED, DataQuality.VERIFIED, DataQuality.STALE, DataQuality.CONFLICTED}
        ),
        DataQuality.VERIFIED: frozenset(
            {DataQuality.VERIFIED, DataQuality.STALE, DataQuality.INCOMPLETE, DataQuality.CONFLICTED}
        ),
        DataQuality.STALE: frozenset({DataQuality.STALE, DataQuality.VERIFIED}),
        DataQuality.INCOMPLETE: frozenset({DataQuality.INCOMPLETE, DataQuality.VERIFIED}),
        DataQuality.CONFLICTED: frozenset({DataQuality.CONFLICTED}),
        DataQuality.INVALID: frozenset({DataQuality.INVALID}),
    }

    @classmethod
    def transition(cls, current: DataQuality, target: DataQuality) -> DataQuality:
        if target not in cls._allowed[current]:
            raise ValueError(f"Illegal data-quality transition: {current} -> {target}")
        return target

    @staticmethod
    def assess_candle(
        candle: Candle,
        *,
        now: datetime,
        interval: timedelta,
        max_age_seconds: int,
        check_freshness: bool = True,
    ) -> QualityAssessment:
        reference = now.astimezone(UTC)
        if candle.open_time > reference:
            return QualityAssessment(
                DataQuality.INVALID,
                ("candle opens in the future",),
            )
        if candle.close_time > reference:
            return QualityAssessment(
                DataQuality.INCOMPLETE,
                ("close_time is in the future; candle is not closed",),
            )

        # Freshness is a dataset-level gate applied to the latest completed
        # candle. Historical candles remain subject to all integrity checks.
        if check_freshness:
            allowed_age_seconds = interval.total_seconds() + max_age_seconds
            age = (reference - candle.close_time.astimezone(UTC)).total_seconds()
            if age > allowed_age_seconds:
                return QualityAssessment(DataQuality.STALE, ("candle exceeds freshness limit",))

        if candle.close_time - candle.open_time != interval:
            return QualityAssessment(DataQuality.INVALID, ("candle duration does not match timeframe",))
        if candle.received_at < candle.observed_at:
            return QualityAssessment(DataQuality.INVALID, ("received_at precedes observed_at",))
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            return QualityAssessment(DataQuality.INVALID, ("OHLC values must be positive",))
        if candle.high < max(candle.open, candle.close):
            return QualityAssessment(DataQuality.INVALID, ("high is below open/close",))
        if candle.low > min(candle.open, candle.close):
            return QualityAssessment(DataQuality.INVALID, ("low is above open/close",))
        if candle.high < candle.low:
            return QualityAssessment(DataQuality.INVALID, ("high is below low",))
        if candle.volume is not None and candle.volume < 0:
            return QualityAssessment(DataQuality.INVALID, ("volume is negative",))
        return QualityAssessment(DataQuality.VERIFIED)
