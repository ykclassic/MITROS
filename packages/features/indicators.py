from collections.abc import Sequence
from decimal import Decimal, getcontext
from itertools import pairwise

ZERO = Decimal("0")
ONE = Decimal("1")

def _require_period(period: int) -> None:
    if period < 1:
        raise ValueError("period must be >= 1")

def _window(values: Sequence[Decimal], period: int) -> Sequence[Decimal] | None:
    _require_period(period)
    return values[-period:] if len(values) >= period else None

def sma(values: Sequence[Decimal], period: int) -> Decimal | None:
    window = _window(values, period)
    if window is None:
        return None
    return sum(window, ZERO) / Decimal(period)

def ema(values: Sequence[Decimal], period: int) -> Decimal | None:
    _require_period(period)
    if len(values) < period:
        return None
    result = sma(values[:period], period)
    assert result is not None
    alpha = Decimal("2") / Decimal(period + 1)
    for value in values[period:]:
        result = (value - result) * alpha + result
    return result

def percentage_return(values: Sequence[Decimal], periods: int = 1) -> Decimal | None:
    _require_period(periods)
    if len(values) <= periods:
        return None
    previous = values[-periods - 1]
    if previous == ZERO:
        return None
    return (values[-1] / previous) - ONE

def rsi(values: Sequence[Decimal], period: int = 14) -> Decimal | None:
    _require_period(period)
    if len(values) <= period:
        return None
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in pairwise(values):
        change = current - previous
        gains.append(max(change, ZERO))
        losses.append(max(-change, ZERO))
    avg_gain = sum(gains[:period], ZERO) / Decimal(period)
    avg_loss = sum(losses[:period], ZERO) / Decimal(period)
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * Decimal(period - 1) + gain) / Decimal(period)
        avg_loss = (avg_loss * Decimal(period - 1) + loss) / Decimal(period)
    if avg_loss == ZERO:
        return Decimal("100") if avg_gain > ZERO else Decimal("50")
    relative_strength = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (ONE + relative_strength))

def true_range(high: Sequence[Decimal], low: Sequence[Decimal], close: Sequence[Decimal]) -> list[Decimal]:
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high, low and close must have equal lengths")
    if not high:
        return []
    result = [high[0] - low[0]]
    for index in range(1, len(high)):
        result.append(max(
            high[index] - low[index],
            abs(high[index] - close[index - 1]),
            abs(low[index] - close[index - 1]),
        ))
    return result

def atr(high: Sequence[Decimal], low: Sequence[Decimal], close: Sequence[Decimal], period: int = 14) -> Decimal | None:
    _require_period(period)
    tr = true_range(high, low, close)
    if len(tr) < period:
        return None
    result = sum(tr[:period], ZERO) / Decimal(period)
    for value in tr[period:]:
        result = (result * Decimal(period - 1) + value) / Decimal(period)
    return result

def bollinger(values: Sequence[Decimal], period: int = 20, stddevs: Decimal = Decimal("2")) -> tuple[Decimal, Decimal, Decimal] | None:
    window = _window(values, period)
    if window is None:
        return None
    mean = sum(window, ZERO) / Decimal(period)
    variance = sum((value - mean) ** 2 for value in window) / Decimal(period)
    std = getcontext().sqrt(variance)
    return mean, mean + stddevs * std, mean - stddevs * std

def macd(values: Sequence[Decimal], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Decimal, Decimal, Decimal] | None:
    if len(values) < slow:
        return None
    fast_ema = _ema_series(values, fast)
    slow_ema = _ema_series(values, slow)
    macd_series = [f - s for f, s in zip(fast_ema[len(fast_ema) - len(slow_ema):], slow_ema)]
    if len(macd_series) < signal:
        return None
    line = macd_series[-1]
    signal_line = ema(macd_series, signal)
    if signal_line is None:
        return None
    return line, signal_line, line - signal_line

def _ema_series(values: Sequence[Decimal], period: int) -> list[Decimal]:
    _require_period(period)
    if len(values) < period:
        return []
    first = sma(values[:period], period)
    assert first is not None
    alpha = Decimal("2") / Decimal(period + 1)
    result = [first]
    current = first
    for value in values[period:]:
        current = (value - current) * alpha + current
        result.append(current)
    return result
