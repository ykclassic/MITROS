from collections.abc import Sequence
from decimal import Decimal
from contracts.intelligence import CRTSnapshot
from packages.market_data.contracts import Candle, DataQuality


def analyze_crt(candles: Sequence[Candle]) -> CRTSnapshot:
    ordered = _validate(candles)
    reference = ordered[-2]
    confirmation = ordered[-1]
    bullish = confirmation.low < reference.low and confirmation.close > reference.low
    bearish = confirmation.high > reference.high and confirmation.close < reference.high
    swept = bullish or bearish
    if bullish:
        direction, target = "BULLISH", reference.high
    elif bearish:
        direction, target = "BEARISH", reference.low
    else:
        direction, target = "NEUTRAL", None
    score = Decimal("0")
    reasons: list[str] = ["reference=previous_completed_candle"]
    if swept:
        score += Decimal("0.5")
        reasons.append("liquidity_sweep_reclaimed")
        body = abs(confirmation.close - confirmation.open)
        rng = confirmation.high - confirmation.low
        if rng > 0 and body / rng >= Decimal("0.6"):
            score += Decimal("0.25")
            reasons.append("displacement")
        if target is not None:
            distance = abs(target - confirmation.close)
            if distance > 0:
                score += Decimal("0.25")
                reasons.append("opposite_range_target_available")
    return CRTSnapshot(direction=direction, reference_high=reference.high,
        reference_low=reference.low, swept=swept,
        confirmation_index=len(ordered) - 1 if swept else None, target=target,
        score=min(score, Decimal("1")), reasons=tuple(reasons))


def _validate(candles: Sequence[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda c: c.open_time)
    if len(ordered) < 2:
        raise ValueError("CRT requires at least 2 candles")
    if any(c.quality is not DataQuality.VERIFIED for c in ordered):
        raise ValueError("CRT requires VERIFIED candles")
    return ordered
