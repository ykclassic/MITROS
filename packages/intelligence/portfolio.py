from decimal import Decimal

from contracts.domain import Direction
from contracts.regime import MarketRegime
from contracts.strategy_portfolio import (
    EvidenceCheck,
    PortfolioEvaluation,
    PortfolioEvaluationInput,
    SignalDisposition,
    StrategyCandidate,
    StrategyContribution,
)

ENGINE_VERSION = "strategy-portfolio-3.0.0"
ZERO = Decimal("0")
ONE = Decimal("1")


def _candidate_contribution(
    candidate: StrategyCandidate,
    regime: MarketRegime,
) -> StrategyContribution:
    reasons = list(candidate.reasons)
    evidence_passed = all(check.passed for check in candidate.evidence)
    regime_supported = regime in candidate.supported_regimes
    eligible = candidate.eligible and evidence_passed and regime_supported
    regime_weight = ONE if regime_supported else ZERO
    effective_weight = candidate.base_weight * regime_weight if eligible else ZERO
    weighted_score = effective_weight * candidate.confidence
    if not candidate.eligible:
        reasons.append("Strategy eligibility rules rejected this candidate.")
    if not evidence_passed:
        reasons.append("One or more strategy evidence checks failed.")
    if not regime_supported:
        reasons.append(f"Strategy is not approved for regime {regime.value}.")
    if candidate.direction is None:
        reasons.append("Strategy did not produce a directional vote.")
    return StrategyContribution(
        strategy_id=candidate.strategy_id,
        strategy_version=candidate.strategy_version,
        direction=candidate.direction,
        eligible=eligible and candidate.direction is not None,
        regime_weight=regime_weight,
        effective_weight=effective_weight,
        confidence=candidate.confidence,
        weighted_score=weighted_score if candidate.direction is not None else ZERO,
        reasons=tuple(reasons),
        evidence=candidate.evidence,
    )


def _alignment(
    direction: Direction,
    data: PortfolioEvaluationInput,
) -> Decimal:
    usable = [
        bias
        for bias in data.timeframe_biases
        if bias.direction is not None and bias.confidence > ZERO
    ]
    if not usable:
        return ZERO
    total = sum((bias.confidence for bias in usable), ZERO)
    if total == ZERO:
        return ZERO
    aligned = sum(
        (bias.confidence for bias in usable if bias.direction == direction),
        ZERO,
    )
    return aligned / total


def _evidence_quality(checks: tuple[EvidenceCheck, ...]) -> Decimal:
    if not checks:
        return ZERO
    total_weight = sum((check.weight for check in checks), ZERO)
    if total_weight == ZERO:
        return ZERO
    passed_weight = sum((check.weight for check in checks if check.passed), ZERO)
    return passed_weight / total_weight


def evaluate_portfolio(data: PortfolioEvaluationInput) -> PortfolioEvaluation:
    """Evaluate strategy votes without executing or authorizing any trade.

    The engine is deterministic: it uses only supplied, timestamped inputs and
    never fetches market data, mutates weights, or bypasses risk/approval gates.
    """
    reasons: list[str] = []
    contributions = tuple(
        _candidate_contribution(candidate, data.regime)
        for candidate in data.candidates
    )
    evidence = tuple(
        check
        for candidate in data.candidates
        for check in candidate.evidence
    ) + tuple(check for bias in data.timeframe_biases for check in bias.evidence)

    disposition = SignalDisposition.WAIT
    direction: Direction | None = None
    quality_score = ZERO
    mtf_alignment = ZERO
    supporting = 0
    opposing = 0

    if not data.data_verified:
        disposition = SignalDisposition.NO_TRADE
        reasons.append("Market data is not verified.")
    elif not data.data_fresh:
        disposition = SignalDisposition.NO_TRADE
        reasons.append("Market data is stale.")
    elif data.news_blocked or data.regime == MarketRegime.NEWS:
        disposition = SignalDisposition.NO_TRADE
        reasons.append("A news/event block is active.")
    elif data.regime == MarketRegime.UNKNOWN:
        reasons.append("Market regime is unknown; wait for a validated regime.")
    elif data.regime_confidence < data.minimum_regime_confidence:
        reasons.append("Regime confidence is below the configured minimum.")
    else:
        long_score = sum(
            (
                item.weighted_score
                for item in contributions
                if item.eligible and item.direction == Direction.LONG
            ),
            ZERO,
        )
        short_score = sum(
            (
                item.weighted_score
                for item in contributions
                if item.eligible and item.direction == Direction.SHORT
            ),
            ZERO,
        )
        total_score = long_score + short_score
        total_weight = sum(
            (item.effective_weight for item in contributions if item.eligible),
            ZERO,
        )
        supporting_items = [
            item
            for item in contributions
            if item.eligible
            and item.direction is not None
            and item.weighted_score > ZERO
        ]
        if total_score == ZERO or total_weight == ZERO:
            reasons.append("No eligible strategy supplied a directional, evidence-backed vote.")
        else:
            if long_score == short_score:
                long_votes = sum(
                    1 for item in supporting_items if item.direction == Direction.LONG
                )
                short_votes = sum(
                    1 for item in supporting_items if item.direction == Direction.SHORT
                )
                supporting = max(long_votes, short_votes)
                opposing = min(long_votes, short_votes)
                reasons.append(
                    "Directional strategy scores are tied; conflict prevents selection. "
                    f"Long votes: {long_votes}; short votes: {short_votes}."
                )
            else:
                direction = Direction.LONG if long_score > short_score else Direction.SHORT
                winning_score = max(long_score, short_score)
                losing_score = min(long_score, short_score)
                supporting = sum(
                    1 for item in supporting_items if item.direction == direction
                )
                opposing = sum(
                    1 for item in supporting_items if item.direction != direction
                )
                directional_strength = winning_score / total_score
                average_confidence = winning_score / max(
                    sum(
                        (
                            item.effective_weight
                            for item in supporting_items
                            if item.direction == direction
                        ),
                        ZERO,
                    ),
                    Decimal("0.00000001"),
                )
                mtf_alignment = _alignment(direction, data)
                evidence_quality = _evidence_quality(evidence)
                conflict_penalty = losing_score / total_score
                quality_score = (
                    Decimal("0.40") * directional_strength
                    + Decimal("0.25") * average_confidence
                    + Decimal("0.20") * mtf_alignment
                    + Decimal("0.15") * evidence_quality
                )
                quality_score = max(ZERO, min(ONE, quality_score))
                if supporting < 1:
                    reasons.append("No supporting strategy remains eligible.")
                if opposing:
                    reasons.append(
                        f"Conflict detected: {opposing} eligible strategy vote(s) oppose "
                        f"the selected direction (opposition share {conflict_penalty:.3f})."
                    )
                if len(evidence) < data.minimum_evidence_checks:
                    reasons.append(
                        f"Insufficient measurable evidence: {len(evidence)} checks supplied; "
                        f"{data.minimum_evidence_checks} required."
                    )
                if any(not check.passed for check in evidence):
                    reasons.append("At least one supplied evidence check failed validation.")
                if mtf_alignment < data.minimum_mtf_alignment:
                    reasons.append(
                        f"Multi-timeframe alignment {mtf_alignment:.3f} is below "
                        f"{data.minimum_mtf_alignment:.3f}."
                    )
                if quality_score < data.minimum_score:
                    reasons.append(
                        f"Quality score {quality_score:.3f} is below "
                        f"{data.minimum_score:.3f}."
                    )
                if (
                    supporting >= 1
                    and len(evidence) >= data.minimum_evidence_checks
                    and all(check.passed for check in evidence)
                    and mtf_alignment >= data.minimum_mtf_alignment
                    and quality_score >= data.minimum_score
                ):
                    disposition = SignalDisposition.QUALIFIED
                    reasons.append("All portfolio, evidence, regime, and MTF gates passed.")
                else:
                    direction = None
                    disposition = SignalDisposition.WAIT
                    reasons.append("Candidate is not qualified; no trade proposal emitted.")

    if not reasons:
        reasons.append("No candidate met the applicable validation rules.")

    return PortfolioEvaluation(
        asset=data.asset,
        as_of=data.as_of,
        disposition=disposition,
        direction=direction,
        quality_score=quality_score,
        mtf_alignment=mtf_alignment,
        regime=data.regime,
        regime_confidence=data.regime_confidence,
        supporting_strategy_count=supporting,
        opposing_strategy_count=opposing,
        contributions=contributions,
        evidence=evidence,
        reasons=tuple(reasons),
        engine_version=ENGINE_VERSION,
    )
