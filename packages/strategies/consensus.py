from collections.abc import Mapping, Sequence
from decimal import Decimal

from contracts.consensus import (
    ConsensusDirection,
    MTFConsensus,
    MTFStrategyVote,
    StrategyConsensus,
)
from contracts.domain import Direction, StrategyVote


class StrategyConsensusEngine:
    """Deterministically aggregates strategy votes without authorizing trades."""

    def __init__(self, minimum_confidence: Decimal = Decimal("0.60")) -> None:
        if not Decimal("0") <= minimum_confidence <= Decimal("1"):
            raise ValueError("minimum_confidence must be between 0 and 1")
        self.minimum_confidence = minimum_confidence

    def combine_strategies(self, votes: Sequence[StrategyVote]) -> StrategyConsensus:
        if not votes:
            return StrategyConsensus(
                direction=ConsensusDirection.NEUTRAL, confidence=Decimal("0"),
                strategy_count=0, aligned_strategy_count=0, reasons=("no strategy votes",),
            )

        active = [v for v in votes if v.direction is not None and v.confidence > 0]
        long_score = sum((v.confidence for v in active if v.direction is Direction.LONG), Decimal("0"))
        short_score = sum((v.confidence for v in active if v.direction is Direction.SHORT), Decimal("0"))
        total = long_score + short_score

        if total == 0 or long_score == short_score:
            direction, confidence, aligned = ConsensusDirection.NEUTRAL, Decimal("0"), 0
        elif long_score > short_score:
            direction, confidence, aligned = ConsensusDirection.LONG, long_score / total, sum(v.direction is Direction.LONG for v in active)
        else:
            direction, confidence, aligned = ConsensusDirection.SHORT, short_score / total, sum(v.direction is Direction.SHORT for v in active)

        if confidence < self.minimum_confidence:
            direction = ConsensusDirection.NEUTRAL

        return StrategyConsensus(
            direction=direction,
            confidence=confidence,
            strategy_count=len(votes),
            aligned_strategy_count=aligned,
            reasons=(f"strategy_votes={len(votes)}", f"active_votes={len(active)}",
                     f"long_score={long_score}", f"short_score={short_score}"),
        )

    def combine_mtf(
        self,
        timeframe_votes: Mapping[str, Sequence[StrategyVote]],
        timeframe_weights: Mapping[str, Decimal] | None = None,
    ) -> MTFConsensus:
        if not timeframe_votes:
            empty = self.combine_strategies(())
            return MTFConsensus(direction=ConsensusDirection.NEUTRAL, confidence=Decimal("0"),
                                alignment=Decimal("0"), timeframes=(), strategy_consensus=empty,
                                reasons=("no timeframe votes",))

        weights = timeframe_weights or {tf: Decimal("1") for tf in timeframe_votes}
        if set(weights) != set(timeframe_votes) or any(w <= 0 for w in weights.values()):
            raise ValueError("timeframe weights must match supplied timeframes and be positive")

        ordered = sorted(timeframe_votes)
        all_votes = [v for tf in ordered for v in timeframe_votes[tf]]
        per_tf: list[MTFStrategyVote] = []
        weighted_long = Decimal("0")
        weighted_short = Decimal("0")
        total_weight = sum((weights[tf] for tf in ordered), Decimal("0"))

        for tf in ordered:
            consensus = self.combine_strategies(timeframe_votes[tf])
            per_tf.append(MTFStrategyVote(timeframe=tf, votes=tuple(timeframe_votes[tf]),
                                          direction=consensus.direction, confidence=consensus.confidence))
            if consensus.direction is ConsensusDirection.LONG:
                weighted_long += weights[tf] * consensus.confidence
            elif consensus.direction is ConsensusDirection.SHORT:
                weighted_short += weights[tf] * consensus.confidence

        score_total = weighted_long + weighted_short
        if score_total == 0 or weighted_long == weighted_short:
            direction, confidence = ConsensusDirection.NEUTRAL, Decimal("0")
        elif weighted_long > weighted_short:
            direction, confidence = ConsensusDirection.LONG, weighted_long / score_total
        else:
            direction, confidence = ConsensusDirection.SHORT, weighted_short / score_total

        if confidence < self.minimum_confidence:
            direction = ConsensusDirection.NEUTRAL

        alignment = max(weighted_long, weighted_short) / total_weight if total_weight else Decimal("0")
        return MTFConsensus(
            direction=direction, confidence=confidence, alignment=min(Decimal("1"), alignment),
            timeframes=tuple(per_tf), strategy_consensus=self.combine_strategies(all_votes),
            reasons=(f"mtf_timeframes={len(ordered)}", f"weighted_long={weighted_long}",
                     f"weighted_short={weighted_short}"),
        )
