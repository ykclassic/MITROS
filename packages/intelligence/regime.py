from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from contracts.regime import MarketRegime, RegimeSnapshot
from packages.market_data.contracts import Candle, DataQuality


class RegimeDetector:
    """Deterministic regime classifier; confidence is regime-fit, never trade probability."""

    MODEL_VERSION = "deterministic-rules-2.0.0"

    def __init__(
        self,
        trend_threshold: Decimal = Decimal("0.02"),
        high_volatility_threshold: Decimal = Decimal("0.03"),
        low_volatility_threshold: Decimal = Decimal("0.005"),
        breakout_threshold: Decimal = Decimal("0.015"),
        minimum_sample: int = 20,
    ) -> None:
        if trend_threshold <= 0 or breakout_threshold <= 0:
            raise ValueError("thresholds must be positive")
        if not Decimal("0") < low_volatility_threshold < high_volatility_threshold:
            raise ValueError("volatility thresholds are invalid")
        if minimum_sample < 20:
            raise ValueError("minimum_sample must be at least 20")
        self.trend_threshold = trend_threshold
        self.high_volatility_threshold = high_volatility_threshold
        self.low_volatility_threshold = low_volatility_threshold
        self.breakout_threshold = breakout_threshold
        self.minimum_sample = minimum_sample

    def classify(self, candles: Sequence[Candle]) -> RegimeSnapshot:
        ordered = self._validate(candles)
        returns = [(c.close / p.close) - Decimal("1") for p, c in pairwise(ordered)]
        volatility = self._stddev(returns)
        net_return = (ordered[-1].close / ordered[0].close) - Decimal("1")
        trend_strength = min(Decimal("1"), abs(net_return) / self.trend_threshold)
        recent = ordered[-min(20, len(ordered)):-1]
        recent_high = max(c.high for c in recent)
        recent_low = min(c.low for c in recent)
        last = ordered[-1]
        breakout = (
            last.close > recent_high * (Decimal("1") + self.breakout_threshold)
            or last.close < recent_low * (Decimal("1") - self.breakout_threshold)
        )
        short_net = (last.close / ordered[-min(10, len(ordered))].close) - Decimal("1")
        long_direction = net_return > 0
        short_direction = short_net > 0
        transition = abs(net_return) >= self.trend_threshold / 2 and long_direction != short_direction

        if breakout:
            regime = MarketRegime.BREAKOUT
        elif volatility >= self.high_volatility_threshold:
            regime = MarketRegime.HIGH_VOLATILITY
        elif transition:
            regime = MarketRegime.TRANSITION
        elif abs(net_return) >= self.trend_threshold:
            regime = MarketRegime.TREND_UP if net_return > 0 else MarketRegime.TREND_DOWN
        elif volatility <= self.low_volatility_threshold:
            regime = MarketRegime.LOW_VOLATILITY
        else:
            regime = MarketRegime.RANGE

        fit = trend_strength if regime in {MarketRegime.TREND_UP, MarketRegime.TREND_DOWN} else (
            min(Decimal("1"), volatility / self.high_volatility_threshold)
            if regime is MarketRegime.HIGH_VOLATILITY else
            min(Decimal("1"), Decimal("1") - volatility / self.low_volatility_threshold)
            if regime is MarketRegime.LOW_VOLATILITY and self.low_volatility_threshold else
            Decimal("0.75")
        )
        return RegimeSnapshot(
            regime=regime,
            confidence=max(Decimal("0"), min(Decimal("1"), fit)),
            trend_strength=trend_strength,
            volatility=volatility,
            sample_size=len(ordered),
            model_version=self.MODEL_VERSION,
            observation_window=(ordered[0].open_time, ordered[-1].close_time),
            timestamp=ordered[-1].close_time,
            reasons=(
                f"net_return={net_return}",
                f"realized_volatility={volatility}",
                f"breakout={breakout}",
                f"transition={transition}",
            ),
        )

    def _validate(self, candles: Sequence[Candle]) -> list[Candle]:
        if len(candles) < self.minimum_sample:
            raise ValueError(f"regime detection requires at least {self.minimum_sample} candles")
        ordered = sorted(candles, key=lambda c: c.open_time)
        if any(c.quality is not DataQuality.VERIFIED for c in ordered):
            raise ValueError("regime detection requires VERIFIED candles")
        for previous, current in pairwise(ordered):
            if current.open_time <= previous.open_time:
                raise ValueError("duplicate or non-increasing candle timestamps")
        first = ordered[0]
        if any(c.asset != first.asset or c.venue != first.venue or c.timeframe != first.timeframe for c in ordered):
            raise ValueError("all candles must share asset, venue and timeframe")
        return ordered

    @staticmethod
    def _stddev(values: Sequence[Decimal]) -> Decimal:
        mean = sum(values, Decimal("0")) / Decimal(len(values))
        variance = sum(((v - mean) ** 2 for v in values), Decimal("0")) / Decimal(len(values))
        return variance.sqrt()
