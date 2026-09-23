from decimal import Decimal

from contracts.consensus import ConsensusDirection
from contracts.domain import Direction, StrategyVote
from packages.strategies.consensus import StrategyConsensusEngine


def vote(strategy: str, direction: Direction | None, confidence: str) -> StrategyVote:
    return StrategyVote(strategy_id=strategy, strategy_version="1.0.0",
                         direction=direction, confidence=Decimal(confidence), reasons=(strategy,))


def test_strategy_consensus_requires_meaningful_majority():
    result = StrategyConsensusEngine().combine_strategies(
        [vote("smc", Direction.LONG, "0.9"), vote("crt", Direction.LONG, "0.8"),
         vote("other", Direction.SHORT, "0.2")]
    )
    assert result.direction is ConsensusDirection.LONG
    assert result.aligned_strategy_count == 2
    assert result.confidence > Decimal("0.8")


def test_strategy_conflict_fails_closed_to_neutral():
    result = StrategyConsensusEngine().combine_strategies(
        [vote("smc", Direction.LONG, "0.8"), vote("crt", Direction.SHORT, "0.8")]
    )
    assert result.direction is ConsensusDirection.NEUTRAL
    assert result.confidence == Decimal("0")


def test_mtf_weighting_and_alignment():
    result = StrategyConsensusEngine().combine_mtf(
        {"1h": [vote("smc", Direction.LONG, "0.8"), vote("crt", Direction.LONG, "0.7")],
         "4h": [vote("smc", Direction.LONG, "0.9"), vote("crt", Direction.SHORT, "0.2")]},
        {"1h": Decimal("1"), "4h": Decimal("2")},
    )
    assert result.direction is ConsensusDirection.LONG
    assert result.alignment > Decimal("0.8")
    assert result.timeframes[0].timeframe == "1h"


def test_mtf_empty_is_neutral():
    result = StrategyConsensusEngine().combine_mtf({})
    assert result.direction is ConsensusDirection.NEUTRAL
    assert result.confidence == Decimal("0")
    assert result.alignment == Decimal("0")


def test_invalid_weights_rejected():
    try:
        StrategyConsensusEngine().combine_mtf(
            {"1h": [vote("smc", Direction.LONG, "0.8")]}, {"4h": Decimal("1")}
        )
    except ValueError as exc:
        assert "weights" in str(exc)
    else:
        raise AssertionError("expected invalid weights to fail")
