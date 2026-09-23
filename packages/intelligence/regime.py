from collections.abc import Sequence
from decimal import Decimal

from contracts.regime import MarketRegime, RegimeSnapshot
from packages.market_data.contracts import Candle, DataQuality


class RegimeDetector:
    """Deterministic regime classification from verified OHLC candles."""

    def __init__(
        self,
        trend_threshold: Decimal = Decimal("0.02"),
        high_volatility_threshold: Decimal = Decimal("0.03"),
        low_volatility_threshold: Decimal = Decimal("0.005"),
        minimum_sample: int = 20,
    ) -> None:
        if not Decimal("0") < trend_threshold:
            raise ValueError("trend_threshold must be positive")
        if not Decimal("0") < low_volatility_threshold < high_volatility_threshold:
            raise ValueError("volatility thresholds are invalid")
        if minimum_sample < 2:
            raise ValueError("minimum_sample must be at least 2")
        self.trend_threshold = trend_threshold
        self.high_volatility_threshold = high_volatility_threshold
        self.low_volatility_threshold = low_volatility_threshold
        self.minimum_sample = minimum_sample

    def classify(self, candles: Sequence[Candle]) -> RegimeSnapshot:
        ordered = self._validate(candles)
        returns = [(c.close / p.close) - Decimal("1") for p, c in zip(ordered, ordered[1:])]
        mean = sum(returns, Decimal("0")) / Decimal(len(returns))
        volatility = self._stddev(returns)
        net_return = (ordered[-1].close / ordered[0].close) - Decimal("1")
        trend_strength = min(Decimal("1"), abs(net_return) / self.trend_threshold)

        if volatility >= self.high_volatility_threshold:
            regime = MarketRegime.HIGH_VOLATILITY
        elif volatility <= self.low_volatility_threshold:
            regime = MarketRegime.LOW_VOLATILITY
        elif abs(net_return) >= self.trend_threshold:
            regime = MarketRegime.TREND_UP if net_return > 0 else MarketRegime.TREND_DOWN
        else:
            regime = MarketRegime.RANGE

        confidence = min(Decimal("1"), max(trend_strength, Decimal("0.5") if regime in {
            MarketRegime.HIGH_VOLATILITY, MarketRegime.LOW_VOLATILITY
        } else Decimal("0")))
        return RegimeSnapshot(
            regime=regime, confidence=confidence, trend_strength=trend_strength,
            volatility=volatility, sample_size=len(ordered),
            reasons=(f"net_return={net_return}", f"volatility={volatility}", f"mean_return={mean}"),
        )

    def _validate(self, candles: Sequence[Candle]) -> list[Candle]:
        if len(candles) < self.minimum_sample:
            raise ValueError(f"regime detection requires at least {self.minimum_sample} candles")
        ordered = sorted(candles, key=lambda c: c.open_time)
        if any(c.quality is not DataQuality.VERIFIED for c in ordered):
            raise ValueError("regime detection requires VERIFIED candles")
        for previous, current in zip(ordered, ordered[1:]):
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
