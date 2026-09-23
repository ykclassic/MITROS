from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from contracts.crt import CRTAnalysis, CRTDirection, CRTRange, CRTSweep
from contracts.domain import Direction, StrategyVote
from packages.market_data.contracts import Candle, DataQuality

from .base import StrategyContext, StrategyPlugin


class CRTStrategy(StrategyPlugin):
    """Deterministic Candle Range Theory strategy."""

    strategy_id = "crt"
    strategy_version = "1.0.0"

    def __init__(self, minimum_confidence: Decimal = Decimal("0.75")) -> None:
        if not Decimal("0") <= minimum_confidence <= Decimal("1"):
            raise ValueError("minimum_confidence must be between 0 and 1")
        self.minimum_confidence = minimum_confidence

    def analyze(self, candles: Sequence[Candle]) -> CRTAnalysis:
        ordered = self._validate(candles)
        reference_index = len(ordered) - 2
        confirmation_index = len(ordered) - 1
        reference = ordered[reference_index]
        latest = ordered[confirmation_index]
        reference_range = CRTRange(
            candle_index=reference_index,
            high=reference.high,
            low=reference.low,
        )

        if latest.high > reference.high and latest.close < reference.high:
            sweep = CRTSweep(
                direction=CRTDirection.BEARISH,
                reference_index=reference_index,
                confirmation_index=confirmation_index,
                swept_price=latest.high,
                reclaim_price=latest.close,
                target_price=reference.low,
            )
            return CRTAnalysis(
                direction=CRTDirection.BEARISH,
                reference_range=reference_range,
                sweep=sweep,
                reasons=(
                    "CRT bearish liquidity sweep above reference high",
                    "latest candle closed back inside reference range",
                    "reference low is the opposing range target",
                ),
            )

        if latest.low < reference.low and latest.close > reference.low:
            sweep = CRTSweep(
                direction=CRTDirection.BULLISH,
                reference_index=reference_index,
                confirmation_index=confirmation_index,
                swept_price=latest.low,
                reclaim_price=latest.close,
                target_price=reference.high,
            )
            return CRTAnalysis(
                direction=CRTDirection.BULLISH,
                reference_range=reference_range,
                sweep=sweep,
                reasons=(
                    "CRT bullish liquidity sweep below reference low",
                    "latest candle closed back inside reference range",
                    "reference high is the opposing range target",
                ),
            )

        return CRTAnalysis(
            direction=CRTDirection.NEUTRAL,
            reference_range=reference_range,
            reasons=("no confirmed CRT range sweep and reclaim",),
        )

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        analysis = self.analyze(context.candles)
        confidence = Decimal("1") if analysis.sweep is not None else Decimal("0")
        direction = None
        if analysis.direction is CRTDirection.BULLISH and confidence >= self.minimum_confidence:
            direction = Direction.LONG
        elif analysis.direction is CRTDirection.BEARISH and confidence >= self.minimum_confidence:
            direction = Direction.SHORT

        return StrategyVote(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            direction=direction,
            confidence=confidence,
            reasons=analysis.reasons,
        )

    @staticmethod
    def _validate(candles: Sequence[Candle]) -> list[Candle]:
        if len(candles) < 2:
            raise ValueError("CRT strategy requires at least 2 candles")

        ordered = sorted(candles, key=lambda candle: candle.open_time)
        if any(c.quality is not DataQuality.VERIFIED for c in ordered):
            raise ValueError("CRT strategy requires VERIFIED candles")
        if any(current.open_time <= previous.open_time for previous, current in pairwise(ordered)):
            raise ValueError("Duplicate or non-increasing candle timestamps")

        first = ordered[0]
        if any(
            c.asset != first.asset
            or c.venue != first.venue
            or c.timeframe != first.timeframe
            for c in ordered
        ):
            raise ValueError("All candles must share asset, venue and timeframe")
        return ordered
