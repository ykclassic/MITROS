from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise
from contracts.intelligence import MarketStructureKind, MarketStructureSnapshot
from packages.market_data.contracts import Candle, DataQuality


def analyze_structure(candles: Sequence[Candle], pivot: int = 2) -> MarketStructureSnapshot:
    ordered = _validate(candles)
    highs: list[tuple[int, Decimal]] = []
    lows: list[tuple[int, Decimal]] = []
    for i in range(pivot, len(ordered) - pivot):
        window = ordered[i - pivot:i + pivot + 1]
        if ordered[i].high == max(c.high for c in window) and ordered[i].high > max(c.high for c in window[:pivot]):
            highs.append((i, ordered[i].high))
        if ordered[i].low == min(c.low for c in window) and ordered[i].low < min(c.low for c in window[:pivot]):
            lows.append((i, ordered[i].low))
    if len(highs) < 2 or len(lows) < 2:
        return MarketStructureSnapshot(kind=MarketStructureKind.UNKNOWN, bias="NEUTRAL",
            swing_highs=tuple(p for _, p in highs), swing_lows=tuple(p for _, p in lows),
            bos=(), choch=())
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]
    ll = lows[-1][1] < lows[-2][1]
    if hh and hl:
        kind, bias = MarketStructureKind.TREND, "BULLISH"
    elif lh and ll:
        kind, bias = MarketStructureKind.TREND, "BEARISH"
    else:
        kind, bias = MarketStructureKind.RANGE, "NEUTRAL"
    bos: list[str] = []
    choch: list[str] = []
    last_close = ordered[-1].close
    if last_close > highs[-1][1]:
        bos.append("BULLISH")
    if last_close < lows[-1][1]:
        bos.append("BEARISH")
    if bias == "BULLISH" and last_close < lows[-1][1]:
        choch.append("BEARISH")
    if bias == "BEARISH" and last_close > highs[-1][1]:
        choch.append("BULLISH")
    strength = min(Decimal("1"), (abs(ordered[-1].close - ordered[0].close) /
        ordered[0].close) * Decimal("10")) if ordered[0].close else Decimal("0")
    return MarketStructureSnapshot(kind=kind, bias=bias,
        swing_highs=tuple(p for _, p in highs[-8:]), swing_lows=tuple(p for _, p in lows[-8:]),
        bos=tuple(bos), choch=tuple(choch), trend_strength=max(Decimal("0"), strength),
        range_high=max(p for _, p in highs) if kind == MarketStructureKind.RANGE else None,
        range_low=min(p for _, p in lows) if kind == MarketStructureKind.RANGE else None)


def _validate(candles: Sequence[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda c: c.open_time)
    if len(ordered) < 7:
        raise ValueError("market structure requires at least 7 candles")
    if any(c.quality is not DataQuality.VERIFIED for c in ordered):
        raise ValueError("market structure requires VERIFIED candles")
    if any(b.open_time <= a.open_time for a, b in pairwise(ordered)):
        raise ValueError("market structure requires strictly increasing timestamps")
    return ordered
