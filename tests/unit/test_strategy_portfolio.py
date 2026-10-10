from datetime import UTC, datetime
from decimal import Decimal

from contracts.domain import Direction
from contracts.regime import MarketRegime
from contracts.strategy_portfolio import (
    EvidenceCheck,
    PortfolioEvaluationInput,
    SignalDisposition,
    StrategyCandidate,
    TimeframeBias,
)
from packages.intelligence.portfolio import ENGINE_VERSION, evaluate_portfolio


def evidence(name: str, observed: str, threshold: str = "0.5") -> EvidenceCheck:
    value = Decimal(observed)
    limit = Decimal(threshold)
    return EvidenceCheck(
        name=name,
        observed=value,
        threshold=limit,
        comparator=">=",
        passed=value >= limit,
        weight=Decimal("1"),
        explanation=f"{name} must be at least {limit}.",
    )


def candidate(
    strategy_id: str = "trend-following",
    direction: Direction | None = Direction.LONG,
    confidence: str = "0.9",
    eligible: bool = True,
    supported_regimes: tuple[MarketRegime, ...] = (MarketRegime.TREND_UP,),
    checks: tuple[EvidenceCheck, ...] | None = None,
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        direction=direction,
        confidence=Decimal(confidence),
        base_weight=Decimal("1"),
        eligible=eligible,
        supported_regimes=supported_regimes,
        timeframe="1h",
        evidence=checks if checks is not None else (
            evidence("trend_strength", "0.8"),
            evidence("momentum", "0.7"),
        ),
        reasons=("Deterministic test candidate.",),
    )


def evaluation_input(**overrides: object) -> PortfolioEvaluationInput:
    values: dict[str, object] = {
        "asset": "BTC/USD",
        "as_of": datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
        "regime": MarketRegime.TREND_UP,
        "regime_confidence": Decimal("0.9"),
        "data_verified": True,
        "data_fresh": True,
        "news_blocked": False,
        "candidates": (candidate(),),
        "timeframe_biases": (
            TimeframeBias(
                timeframe="4h",
                direction=Direction.LONG,
                confidence=Decimal("0.9"),
            ),
            TimeframeBias(
                timeframe="1h",
                direction=Direction.LONG,
                confidence=Decimal("0.8"),
            ),
            TimeframeBias(
                timeframe="15m",
                direction=Direction.LONG,
                confidence=Decimal("0.7"),
            ),
        ),
    }
    values.update(overrides)
    return PortfolioEvaluationInput.model_validate(values)


def test_qualified_signal_has_measurable_evidence_and_version() -> None:
    result = evaluate_portfolio(evaluation_input())

    assert result.disposition == SignalDisposition.QUALIFIED
    assert result.direction == Direction.LONG
    assert result.quality_score >= Decimal("0.65")
    assert result.mtf_alignment == Decimal("1")
    assert len(result.evidence) >= 2
    assert all(item.passed for item in result.evidence)
    assert result.engine_version == ENGINE_VERSION


def test_stale_data_fails_closed_to_no_trade() -> None:
    result = evaluate_portfolio(evaluation_input(data_fresh=False))

    assert result.disposition == SignalDisposition.NO_TRADE
    assert result.direction is None
    assert any("stale" in reason.lower() for reason in result.reasons)


def test_unverified_data_fails_closed_to_no_trade() -> None:
    result = evaluate_portfolio(evaluation_input(data_verified=False))

    assert result.disposition == SignalDisposition.NO_TRADE
    assert result.direction is None


def test_news_block_fails_closed_to_no_trade() -> None:
    result = evaluate_portfolio(evaluation_input(news_blocked=True))

    assert result.disposition == SignalDisposition.NO_TRADE
    assert result.direction is None


def test_unknown_regime_returns_wait() -> None:
    result = evaluate_portfolio(
        evaluation_input(regime=MarketRegime.UNKNOWN, candidates=())
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None


def test_ineligible_strategy_cannot_generate_signal() -> None:
    result = evaluate_portfolio(
        evaluation_input(candidates=(candidate(eligible=False),))
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None
    assert any("eligibility" in reason.lower() for item in result.contributions for reason in item.reasons)


def test_failed_evidence_prevents_qualification() -> None:
    result = evaluate_portfolio(
        evaluation_input(
            candidates=(
                candidate(
                    checks=(
                        evidence("trend_strength", "0.8"),
                        evidence("spread_quality", "0.1", "0.5"),
                    )
                ),
            )
        )
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None
    assert any("evidence check failed" in reason.lower() for reason in result.reasons)


def test_regime_mismatch_makes_strategy_ineligible() -> None:
    result = evaluate_portfolio(
        evaluation_input(
            candidates=(
                candidate(supported_regimes=(MarketRegime.RANGE,)),
            )
        )
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None


def test_opposing_votes_are_explained_and_not_silently_ignored() -> None:
    result = evaluate_portfolio(
        evaluation_input(
            candidates=(
                candidate("trend", Direction.LONG, "0.8"),
                candidate("mean-reversion", Direction.SHORT, "0.8"),
            )
        )
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None
    assert result.opposing_strategy_count == 1
    assert any("conflict detected" in reason.lower() for reason in result.reasons)


def test_low_mtf_alignment_returns_wait() -> None:
    result = evaluate_portfolio(
        evaluation_input(
            timeframe_biases=(
                TimeframeBias(
                    timeframe="4h",
                    direction=Direction.SHORT,
                    confidence=Decimal("0.9"),
                ),
                TimeframeBias(
                    timeframe="1h",
                    direction=Direction.LONG,
                    confidence=Decimal("0.1"),
                ),
            )
        )
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None
    assert any("alignment" in reason.lower() for reason in result.reasons)


def test_regime_confidence_below_floor_returns_wait() -> None:
    result = evaluate_portfolio(
        evaluation_input(regime_confidence=Decimal("0.2"))
    )

    assert result.disposition == SignalDisposition.WAIT
    assert result.direction is None
