from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from contracts.domain import Direction, StrategyVote
from contracts.smc import (
    DirectionBias,
    FairValueGap,
    LiquiditySweep,
    OrderBlock,
    SMCAnalysis,
    StructureBreak,
    StructureBreakKind,
    StructureKind,
    SwingPoint,
)
from packages.market_data.contracts import Candle, DataQuality
from .base import StrategyContext, StrategyPlugin

class SMCStrategy(StrategyPlugin):
    strategy_id = "smc"
    strategy_version = "1.0.0"

    def __init__(self, swing_strength: int = 2, minimum_confidence: Decimal = Decimal("0.55")) -> None:
        if swing_strength < 1:
            raise ValueError("swing_strength must be >= 1")
        if not Decimal("0") <= minimum_confidence <= Decimal("1"):
            raise ValueError("minimum_confidence must be between 0 and 1")
        self.swing_strength = swing_strength
        self.minimum_confidence = minimum_confidence

    def analyze(self, candles: Sequence[Candle]) -> SMCAnalysis:
        ordered = self._validate(candles)
        swings = self._swings(ordered, self.swing_strength)
        events = self._structure_events(ordered, swings)
        sweeps = self._liquidity_sweeps(ordered, swings)
        gaps = self._fair_value_gaps(ordered)
        blocks = self._order_blocks(ordered, events)
        bias = self._bias(events, sweeps, gaps, blocks)
        return SMCAnalysis(
            bias=bias,
            swings=tuple(swings),
            structure_events=tuple(events),
            liquidity_sweeps=tuple(sweeps),
            fair_value_gaps=tuple(gaps),
            order_blocks=tuple(blocks),
            reasons=tuple(self._reasons(bias, events, sweeps, gaps, blocks)),
        )

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        analysis = self.analyze(context.candles)
        confidence = self._confidence(analysis)
        direction = None
        if analysis.bias is DirectionBias.BULLISH:
            direction = Direction.LONG
        elif analysis.bias is DirectionBias.BEARISH:
            direction = Direction.SHORT
        if direction is not None and confidence < self.minimum_confidence:
            direction = None
        reasons = analysis.reasons
        if direction is None and analysis.bias is not DirectionBias.NEUTRAL:
            reasons = reasons + ("confluence below minimum threshold",)
        return StrategyVote(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            direction=direction,
            confidence=confidence,
            reasons=reasons,
        )

    @staticmethod
    def _validate(candles: Sequence[Candle]) -> list[Candle]:
        if len(candles) < 7:
            raise ValueError("SMC strategy requires at least 7 candles")
        ordered = sorted(candles, key=lambda candle: candle.open_time)
        if any(c.quality is not DataQuality.VERIFIED for c in ordered):
            raise ValueError("SMC strategy requires VERIFIED candles")
        if any(current.open_time <= previous.open_time for previous, current in pairwise(ordered)):
            raise ValueError("Duplicate or non-increasing candle timestamps")
        first = ordered[0]
        if any(c.asset != first.asset or c.venue != first.venue or c.timeframe != first.timeframe for c in ordered):
            raise ValueError("All candles must share asset, venue and timeframe")
        return ordered

    @staticmethod
    def _swings(candles: Sequence[Candle], strength: int) -> list[SwingPoint]:
        result: list[SwingPoint] = []
        for i in range(strength, len(candles) - strength):
            current = candles[i]
            neighbours = (*candles[i - strength:i], *candles[i + 1:i + strength + 1])
            if all(current.high > candle.high for candle in neighbours):
                result.append(SwingPoint(kind=StructureKind.HIGH, index=i, price=current.high, occurred_at=current.close_time, strength=strength))
            if all(current.low < candle.low for candle in neighbours):
                result.append(SwingPoint(kind=StructureKind.LOW, index=i, price=current.low, occurred_at=current.close_time, strength=strength))
        return result

    @staticmethod
    def _structure_events(candles: Sequence[Candle], swings: Sequence[SwingPoint]) -> list[StructureBreak]:
        candidates: list[StructureBreak] = []
        for swing in swings:
            direction = DirectionBias.BULLISH if swing.kind is StructureKind.HIGH else DirectionBias.BEARISH
            if direction is DirectionBias.BULLISH:
                confirmations = [i for i in range(swing.index + 1, len(candles)) if candles[i].close > swing.price]
            else:
                confirmations = [i for i in range(swing.index + 1, len(candles)) if candles[i].close < swing.price]
            if confirmations:
                candidates.append(StructureBreak(
                    kind=StructureBreakKind.BOS,
                    direction=direction,
                    broken_price=swing.price,
                    swing_index=swing.index,
                    confirmation_index=confirmations[0],
                ))
        candidates.sort(key=lambda event: event.confirmation_index)
        for i in range(1, len(candidates)):
            if candidates[i].direction is not candidates[i - 1].direction:
                candidates[i] = candidates[i].model_copy(update={"kind": StructureBreakKind.CHOCH})
        return candidates[-6:]

    @staticmethod
    def _liquidity_sweeps(candles: Sequence[Candle], swings: Sequence[SwingPoint]) -> list[LiquiditySweep]:
        latest_index = len(candles) - 1
        latest = candles[latest_index]
        result: list[LiquiditySweep] = []
        for swing in swings[-8:]:
            if swing.index >= latest_index:
                continue
            if swing.kind is StructureKind.HIGH and latest.high > swing.price and latest.close < swing.price:
                result.append(LiquiditySweep(direction=DirectionBias.BEARISH, level=swing.price, candle_index=latest_index, reclaimed=True))
            elif swing.kind is StructureKind.LOW and latest.low < swing.price and latest.close > swing.price:
                result.append(LiquiditySweep(direction=DirectionBias.BULLISH, level=swing.price, candle_index=latest_index, reclaimed=True))
        return result

    @staticmethod
    def _fair_value_gaps(candles: Sequence[Candle]) -> list[FairValueGap]:
        result: list[FairValueGap] = []
        for i in range(2, len(candles)):
            left, right = candles[i - 2], candles[i]
            if right.low > left.high:
                result.append(FairValueGap(direction=DirectionBias.BULLISH, lower=left.high, upper=right.low, candle_index=i))
            elif right.high < left.low:
                result.append(FairValueGap(direction=DirectionBias.BEARISH, lower=right.high, upper=left.low, candle_index=i))
        return result

    @staticmethod
    def _order_blocks(candles: Sequence[Candle], events: Sequence[StructureBreak]) -> list[OrderBlock]:
        result: list[OrderBlock] = []
        for event in events:
            for i in range(event.confirmation_index - 1, -1, -1):
                candle = candles[i]
                if event.direction is DirectionBias.BULLISH and candle.close < candle.open:
                    result.append(OrderBlock(direction=DirectionBias.BULLISH, lower=candle.low, upper=candle.high, candle_index=i))
                    break
                if event.direction is DirectionBias.BEARISH and candle.close > candle.open:
                    result.append(OrderBlock(direction=DirectionBias.BEARISH, lower=candle.low, upper=candle.high, candle_index=i))
                    break
        return result[-6:]

    @staticmethod
    def _bias(events: Sequence[StructureBreak], sweeps: Sequence[LiquiditySweep], gaps: Sequence[FairValueGap], blocks: Sequence[OrderBlock]) -> DirectionBias:
        scores = {DirectionBias.BULLISH: 0, DirectionBias.BEARISH: 0}
        for event in events[-2:]:
            scores[event.direction] += 3 if event.kind is StructureBreakKind.CHOCH else 2
        for sweep in sweeps[-2:]:
            scores[sweep.direction] += 2
        for gap in gaps[-2:]:
            scores[gap.direction] += 1
        for block in blocks[-2:]:
            scores[block.direction] += 1
        if scores[DirectionBias.BULLISH] == scores[DirectionBias.BEARISH]:
            return DirectionBias.NEUTRAL
        return DirectionBias.BULLISH if scores[DirectionBias.BULLISH] > scores[DirectionBias.BEARISH] else DirectionBias.BEARISH

    @staticmethod
    def _confidence(analysis: SMCAnalysis) -> Decimal:
        components = sum((
            bool(analysis.structure_events),
            bool(analysis.liquidity_sweeps),
            bool(analysis.fair_value_gaps),
            bool(analysis.order_blocks),
        ))
        return min(Decimal("1"), Decimal(components) / Decimal("4"))

    @staticmethod
    def _reasons(bias: DirectionBias, events: Sequence[StructureBreak], sweeps: Sequence[LiquiditySweep], gaps: Sequence[FairValueGap], blocks: Sequence[OrderBlock]) -> list[str]:
        reasons = [f"SMC bias={bias.value}"]
        if events:
            reasons.append(f"structure={events[-1].kind.value}:{events[-1].direction.value}")
        if sweeps:
            reasons.append(f"liquidity_sweep={sweeps[-1].direction.value}")
        if gaps:
            reasons.append(f"fair_value_gap={gaps[-1].direction.value}")
        if blocks:
            reasons.append(f"order_block={blocks[-1].direction.value}")
        return reasons
