from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING

from contracts.domain import Provenance
from packages.market_data.contracts import Candle, DataQuality

from .contracts import FeatureEngineConfig, FeatureSet
from .indicators import atr, bollinger, ema, macd, percentage_return, rsi, sma

if TYPE_CHECKING:
    from contracts.features import FeatureSnapshot

DEFAULT_FEATURE_SET = FeatureSet(
    key="technical_core",
    version="1.0.0",
    indicators=(
        "return_1", "sma_20", "ema_20", "ema_50",
        "rsi_14", "macd_12_26", "macd_signal_9", "macd_histogram_12_26_9",
        "atr_14", "bb_mid_20", "bb_upper_20", "bb_lower_20", "bb_width_20",
    ),
)

class FeatureEngine:
    """Deterministic feature computation over completed, validated candles."""

    def __init__(self, config: FeatureEngineConfig | None = None) -> None:
        self.config = config or FeatureEngineConfig(
            feature_set=DEFAULT_FEATURE_SET,
            minimum_history=50,
        )

    def compute(self, candles: Sequence[Candle]) -> dict[str, Decimal]:
        ordered = self._validate(candles)
        closes = [c.close for c in ordered]
        highs = [c.high for c in ordered]
        lows = [c.low for c in ordered]
        cfg = self.config
        features: dict[str, Decimal | None] = {
            "return_1": percentage_return(closes, 1),
            "sma_20": sma(closes, cfg.sma_period),
            "ema_20": ema(closes, 20),
            "ema_50": ema(closes, 50),
            "rsi_14": rsi(closes, cfg.rsi_period),
            "atr_14": atr(highs, lows, closes, cfg.atr_period),
        }
        macd_values = macd(closes, cfg.ema_fast_period, cfg.ema_slow_period, cfg.macd_signal_period)
        if macd_values is not None:
            features.update({
                "macd_12_26": macd_values[0],
                "macd_signal_9": macd_values[1],
                "macd_histogram_12_26_9": macd_values[2],
            })
        bands = bollinger(closes, cfg.bollinger_period, cfg.bollinger_stddevs)
        if bands is not None:
            middle, upper, lower = bands
            features.update({
                "bb_mid_20": middle,
                "bb_upper_20": upper,
                "bb_lower_20": lower,
                "bb_width_20": (upper - lower) / middle if middle != 0 else Decimal("0"),
            })
        missing = [name for name in cfg.feature_set.indicators if features.get(name) is None]
        if missing:
            raise ValueError(
                f"Insufficient history for feature set {cfg.feature_set.key}: {', '.join(missing)}"
            )
        return {name: value for name in cfg.feature_set.indicators if (value := features[name]) is not None}

    def snapshot(self, candles: Sequence[Candle]) -> FeatureSnapshot:
        from contracts.features import FeatureSnapshot
        ordered = self._validate(candles)
        latest = ordered[-1]
        return FeatureSnapshot(
            asset=latest.asset,
            venue=latest.venue,
            timeframe=latest.timeframe,
            as_of=latest.close_time,
            feature_set_version=self.config.feature_set.version,
            values=self.compute(ordered),
            required_history=self.config.minimum_history,
            provenance=(Provenance(
                source=latest.provider,
                source_version=latest.provider_version,
                observed_at=latest.observed_at,
                received_at=latest.received_at,
            ),),
        )

    def _validate(self, candles: Sequence[Candle]) -> list[Candle]:
        if not candles:
            raise ValueError("At least one candle is required")
        ordered = sorted(candles, key=lambda candle: candle.open_time)
        first = ordered[0]
        if any(c.asset != first.asset or c.venue != first.venue or c.timeframe != first.timeframe for c in ordered):
            raise ValueError("All candles must share asset, venue and timeframe")
        if any(c.quality != DataQuality.VERIFIED for c in ordered):
            raise ValueError("Feature computation requires VERIFIED candles")
        if any(current.open_time <= previous.open_time for previous, current in pairwise(ordered)):
            raise ValueError("Duplicate or non-increasing candle timestamps")
        if len(ordered) < self.config.minimum_history:
            raise ValueError(f"At least {self.config.minimum_history} completed candles are required")
        return ordered
