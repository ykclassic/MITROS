from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from contracts.domain import Direction
from contracts.regime import MarketRegime


class SignalDisposition(StrEnum):
    QUALIFIED = "QUALIFIED"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class EvidenceCheck(BaseModel):
    """One auditable, numeric check supporting or blocking a signal."""

    model_config = ConfigDict(frozen=True)

    name: str
    observed: Decimal
    threshold: Decimal
    comparator: str
    passed: bool
    weight: Decimal = Field(ge=0, le=1)
    explanation: str


class StrategyCandidate(BaseModel):
    """A strategy's deterministic opinion for one asset and decision timestamp."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    direction: Direction | None
    confidence: Decimal = Field(ge=0, le=1)
    base_weight: Decimal = Field(gt=0, le=1)
    eligible: bool
    supported_regimes: tuple[MarketRegime, ...]
    timeframe: str = Field(min_length=1)
    evidence: tuple[EvidenceCheck, ...] = ()
    reasons: tuple[str, ...] = ()


class TimeframeBias(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeframe: str = Field(min_length=1)
    direction: Direction | None
    confidence: Decimal = Field(ge=0, le=1)
    evidence: tuple[EvidenceCheck, ...] = ()


class PortfolioEvaluationInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str = Field(min_length=1)
    as_of: datetime
    regime: MarketRegime
    regime_confidence: Decimal = Field(ge=0, le=1)
    data_verified: bool
    data_fresh: bool
    news_blocked: bool = False
    candidates: tuple[StrategyCandidate, ...]
    timeframe_biases: tuple[TimeframeBias, ...]
    minimum_score: Decimal = Field(default=Decimal("0.65"), ge=0, le=1)
    minimum_mtf_alignment: Decimal = Field(default=Decimal("0.60"), ge=0, le=1)
    minimum_regime_confidence: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
    minimum_evidence_checks: int = Field(default=2, ge=1)


class StrategyContribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    strategy_version: str
    direction: Direction | None
    eligible: bool
    regime_weight: Decimal = Field(ge=0, le=1)
    effective_weight: Decimal = Field(ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1)
    weighted_score: Decimal = Field(ge=0, le=1)
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceCheck, ...]


class PortfolioEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    as_of: datetime
    disposition: SignalDisposition
    direction: Direction | None
    quality_score: Decimal = Field(ge=0, le=1)
    mtf_alignment: Decimal = Field(ge=0, le=1)
    regime: MarketRegime
    regime_confidence: Decimal = Field(ge=0, le=1)
    supporting_strategy_count: int = Field(ge=0)
    opposing_strategy_count: int = Field(ge=0)
    contributions: tuple[StrategyContribution, ...]
    evidence: tuple[EvidenceCheck, ...]
    reasons: tuple[str, ...]
    engine_version: str
