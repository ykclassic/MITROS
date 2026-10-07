from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise
from contracts.intelligence import QuantitativeMetrics
from packages.market_data.contracts import Candle, DataQuality


def analyze_quantitative(candles: Sequence[Candle], peer_closes: Sequence[Decimal] | None = None) -> QuantitativeMetrics:
    ordered = _validate(candles)
    returns = [(b.close / a.close) - Decimal("1") for a, b in pairwise(ordered)]
    mean = _mean(returns)
    variance = _mean([(r - mean) ** 2 for r in returns])
    volatility = variance.sqrt()
    atr = _atr(ordered, 14)
    momentum = (ordered[-1].close / ordered[-min(11, len(ordered) - 1) - 1].close) - Decimal("1")
    volumes = [c.volume for c in ordered if c.volume is not None]
    volume_mean = _mean(volumes) if volumes else Decimal("0")
    volume_ratio = volumes[-1] / volume_mean if volumes and volume_mean else Decimal("0")
    m3 = _mean([(r - mean) ** 3 for r in returns])
    m4 = _mean([(r - mean) ** 4 for r in returns])
    skew = m3 / (volatility ** 3) if volatility else Decimal("0")
    kurtosis = m4 / (volatility ** 4) - Decimal("3") if volatility else Decimal("0")
    autocorr = _autocorrelation(returns)
    correlation = _correlation(ordered, peer_closes) if peer_closes is not None else None
    return QuantitativeMetrics(
        return_1=returns[-1], return_window=(ordered[-1].close / ordered[0].close) - Decimal("1"),
        atr=atr, realized_volatility=volatility, momentum=momentum,
        volume_mean=volume_mean, volume_ratio=volume_ratio, return_skew=skew,
        return_kurtosis_excess=kurtosis, autocorrelation_1=autocorr, correlation=correlation)


def _atr(candles: Sequence[Candle], period: int) -> Decimal:
    tr: list[Decimal] = [candles[0].high - candles[0].low]
    for prev, cur in pairwise(candles):
        tr.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    if len(tr) < period:
        return _mean(tr)
    result = _mean(tr[:period])
    for value in tr[period:]:
        result = (result * Decimal(period - 1) + value) / Decimal(period)
    return result


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")


def _autocorrelation(values: Sequence[Decimal]) -> Decimal:
    if len(values) < 3:
        return Decimal("0")
    mean = _mean(values)
    denominator = sum((v - mean) ** 2 for v in values)
    if denominator == 0:
        return Decimal("0")
    numerator = sum((a - mean) * (b - mean) for a, b in pairwise(values))
    return max(Decimal("-1"), min(Decimal("1"), numerator / denominator))


def _correlation(candles: Sequence[Candle], peer: Sequence[Decimal]) -> Decimal | None:
    if len(peer) != len(candles):
        raise ValueError("peer series must match candle length")
    x = [c.close for c in candles]
    y = list(peer)
    mx, my = _mean(x), _mean(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = sum((a - mx) ** 2 for a in x)
    dy = sum((b - my) ** 2 for b in y)
    if dx == 0 or dy == 0:
        return Decimal("0")
    return max(Decimal("-1"), min(Decimal("1"), numerator / (dx * dy).sqrt()))


def _validate(candles: Sequence[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda c: c.open_time)
    if len(ordered) < 20:
        raise ValueError("quantitative intelligence requires at least 20 candles")
    if any(c.quality is not DataQuality.VERIFIED for c in ordered):
        raise ValueError("quantitative intelligence requires VERIFIED candles")
    return ordered
