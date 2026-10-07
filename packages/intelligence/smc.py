from collections.abc import Sequence
from decimal import Decimal
from contracts.intelligence import ContextKind, SMCContextSnapshot
from packages.market_data.contracts import Candle, DataQuality


def analyze_smc(candles: Sequence[Candle]) -> SMCContextSnapshot:
    ordered = _validate(candles)
    fvg: list[tuple[str, Decimal, Decimal]] = []
    blocks: list[tuple[str, Decimal, Decimal]] = []
    mitigation: list[str] = []
    for i in range(2, len(ordered)):
        left, middle, right = ordered[i - 2], ordered[i - 1], ordered[i]
        if right.low > left.high:
            fvg.append(("BULLISH", left.high, right.low))
        if right.high < left.low:
            fvg.append(("BEARISH", right.high, left.low))
        if middle.close > middle.open and middle.close > left.high:
            blocks.append(("BULLISH", left.low, left.high))
        if middle.close < middle.open and middle.close < left.low:
            blocks.append(("BEARISH", left.low, left.high))
    recent_high = max(c.high for c in ordered)
    recent_low = min(c.low for c in ordered)
    midpoint = (recent_high + recent_low) / Decimal("2")
    price = ordered[-1].close
    pd = ContextKind.PREMIUM if price > midpoint else ContextKind.DISCOUNT if price < midpoint else ContextKind.EQUILIBRIUM
    displacement = abs(ordered[-1].close - ordered[-1].open) > (ordered[-1].high - ordered[-1].low) * Decimal("0.6")
    for direction, low, high in blocks[-4:]:
        if low <= price <= high:
            mitigation.append(direction)
    return SMCContextSnapshot(fvg=tuple(fvg[-8:]), order_blocks=tuple(blocks[-8:]),
        premium_discount=pd, displacement=displacement, mitigation=tuple(mitigation))


def _validate(candles: Sequence[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda c: c.open_time)
    if len(ordered) < 3:
        raise ValueError("SMC analysis requires at least 3 candles")
    if any(c.quality is not DataQuality.VERIFIED for c in ordered):
        raise ValueError("SMC analysis requires VERIFIED candles")
    return ordered
