from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from contracts.domain import StrategyVote


class ConsensusDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class MTFStrategyVote(BaseModel):
    model_config = ConfigDict(frozen=True)
    timeframe: str
    votes: tuple[StrategyVote, ...]
    direction: ConsensusDirection
    confidence: Decimal = Field(ge=0, le=1)


class StrategyConsensus(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: ConsensusDirection
    confidence: Decimal = Field(ge=0, le=1)
    strategy_count: int = Field(ge=0)
    aligned_strategy_count: int = Field(ge=0)
    reasons: tuple[str, ...] = ()


class MTFConsensus(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: ConsensusDirection
    confidence: Decimal = Field(ge=0, le=1)
    alignment: Decimal = Field(ge=0, le=1)
    timeframes: tuple[MTFStrategyVote, ...]
    strategy_consensus: StrategyConsensus
    reasons: tuple[str, ...] = ()
