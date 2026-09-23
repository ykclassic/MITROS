from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from contracts.regime import StatisticalSnapshot
from packages.market_data.contracts import Candle, DataQuality


class StatisticalEngine:
    """Deterministic descriptive statistics over verified candle returns."""

    def __init__(self, minimum_sample: int = 20) -> None:
        if minimum_sample < 3:
            raise ValueError("minimum_sample must be at least 3")
        self.minimum_sample = minimum_sample

    def analyze(self, candles: Sequence[Candle]) -> StatisticalSnapshot:
        ordered = self._validate(candles)
        returns = [(c.close / p.close) - Decimal("1") for p, c in pairwise(ordered)]
        mean = sum(returns, Decimal("0")) / Decimal(len(returns))
        volatility = self._stddev(returns)
        wins = sum(r > 0 for r in returns)
        downside = [r for r in returns if r < 0]
        downside_deviation = self._stddev(downside) if len(downside) >= 2 else Decimal("0")
        autocorrelation = self._autocorrelation(returns)
        z = mean / volatility if volatility else Decimal("0")
        return StatisticalSnapshot(
            sample_size=len(returns), mean_return=mean, volatility=volatility,
            win_rate=Decimal(wins) / Decimal(len(returns)),
            downside_deviation=downside_deviation,
            autocorrelation_1=autocorrelation, z_score=z,
            reasons=(f"returns={len(returns)}", f"wins={wins}"),
        )

    def _validate(self, candles: Sequence[Candle]) -> list[Candle]:
        if len(candles) < self.minimum_sample:
            raise ValueError(f"statistical analysis requires at least {self.minimum_sample} candles")
        ordered = sorted(candles, key=lambda c: c.open_time)
        if any(c.quality is not DataQuality.VERIFIED for c in ordered):
            raise ValueError("statistical analysis requires VERIFIED candles")
        for previous, current in pairwise(ordered):
            if current.open_time <= previous.open_time:
                raise ValueError("duplicate or non-increasing candle timestamps")
        first = ordered[0]
        if any(c.asset != first.asset or c.venue != first.venue or c.timeframe != first.timeframe for c in ordered):
            raise ValueError("all candles must share asset, venue and timeframe")
        return ordered

    @staticmethod
    def _stddev(values: Sequence[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        mean = sum(values, Decimal("0")) / Decimal(len(values))
        variance = sum(((v - mean) ** 2 for v in values), Decimal("0")) / Decimal(len(values))
        return variance.sqrt()

    @staticmethod
    def _autocorrelation(values: Sequence[Decimal]) -> Decimal:
        if len(values) < 3:
            return Decimal("0")
        mean = sum(values, Decimal("0")) / Decimal(len(values))
        numerator = sum(((a - mean) * (b - mean) for a, b in pairwise(values)), Decimal("0"))
        denominator = sum(((v - mean) ** 2 for v in values), Decimal("0"))
        if denominator == 0:
            return Decimal("0")
        return max(Decimal("-1"), min(Decimal("1"), numerator / denominator))
