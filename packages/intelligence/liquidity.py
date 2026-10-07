from collections.abc import Sequence
from decimal import Decimal
from contracts.intelligence import LiquidityKind, LiquiditySnapshot
from packages.market_data.contracts import Candle, DataQuality


def analyze_liquidity(candles: Sequence[Candle], tolerance: Decimal = Decimal("0.001")) -> LiquiditySnapshot:
    ordered = _validate(candles)
    levels: list[tuple[LiquidityKind, Decimal]] = []
    pools: list[Decimal] = []
    highs = [c.high for c in ordered]
    lows = [c.low for c in ordered]
    recent_high, recent_low = max(highs[:-1]), min(lows[:-1])
    levels.extend(((LiquidityKind.PDH, recent_high), (LiquidityKind.PDL, recent_low)))
    for kind, values in ((LiquidityKind.EQH, highs), (LiquidityKind.EQL, lows)):
        if len(values) >= 3:
            a, b = values[-2], values[-1]
            scale = max(abs(a), abs(b), Decimal("1"))
            if abs(a - b) / scale <= tolerance:
                level = (a + b) / Decimal("2")
                levels.append((kind, level))
                pools.append(level)
    session = _session(ordered[-1].open_time.hour)
    session_candles = [c for c in ordered if _session(c.open_time.hour) == session]
    if session_candles:
        levels.extend(((LiquidityKind.SESSION_HIGH, max(c.high for c in session_candles)),
                       (LiquidityKind.SESSION_LOW, min(c.low for c in session_candles))))
    last = ordered[-1]
    sweeps: list[str] = []
    if last.high > recent_high and last.close < recent_high:
        sweeps.append("HIGH_LIQUIDITY_SWEEP")
    if last.low < recent_low and last.close > recent_low:
        sweeps.append("LOW_LIQUIDITY_SWEEP")
    return LiquiditySnapshot(levels=tuple(levels), sweeps=tuple(sweeps),
        pools=tuple(sorted(set(pools))), session=session)


def _session(hour: int) -> str:
    if 7 <= hour < 13:
        return "LONDON"
    if 13 <= hour < 21:
        return "NEW_YORK"
    if hour >= 21 or hour < 7:
        return "ASIA_OFF"
    return "GLOBAL"


def _validate(candles: Sequence[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda c: c.open_time)
    if len(ordered) < 3:
        raise ValueError("liquidity analysis requires at least 3 candles")
    if any(c.quality is not DataQuality.VERIFIED for c in ordered):
        raise ValueError("liquidity analysis requires VERIFIED candles")
    return ordered
