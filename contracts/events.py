from datetime import datetime
from collections.abc import Mapping
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    MARKET_DATA_UPDATED = "MarketDataUpdated"
    FEATURES_COMPUTED = "FeaturesComputed"
    REGIME_DETECTED = "RegimeDetected"
    STRATEGY_SIGNAL_GENERATED = "StrategySignalGenerated"
    CONSENSUS_EVALUATED = "ConsensusEvaluated"
    RISK_EVALUATED = "RiskEvaluated"
    TRADE_PROPOSAL_CREATED = "TradeProposalCreated"
    APPROVAL_GRANTED = "ApprovalGranted"
    APPROVAL_REJECTED = "ApprovalRejected"
    ORDER_SUBMITTED = "OrderSubmitted"
    ORDER_FILLED = "OrderFilled"
    POSITION_UPDATED = "PositionUpdated"
    TRADE_CLOSED = "TradeClosed"
    OUTCOME_RECORDED = "OutcomeRecorded"
    STRATEGY_PERFORMANCE_UPDATED = "StrategyPerformanceUpdated"
    MODEL_VALIDATED = "ModelValidated"
    MODEL_PROMOTED = "ModelPromoted"
    MODEL_PREDICTION_GENERATED = "ModelPredictionGenerated"
    MODEL_DRIFT_DETECTED = "ModelDriftDetected"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    aggregate_id: UUID
    occurred_at: datetime
    recorded_at: datetime
    producer: str
    producer_version: str
    correlation_id: UUID
    causation_id: UUID | None = None
    schema_version: int = 1
    payload: Mapping[str, object]
    provenance: list[Mapping[str, object]]
