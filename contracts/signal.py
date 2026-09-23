from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from contracts.domain import Direction, StrategyVote

class SignalState(StrEnum):
    GENERATED="GENERATED"; ACTIVE="ACTIVE"; INVALIDATED="INVALIDATED"; EXPIRED="EXPIRED"
    APPROVED="APPROVED"; REJECTED="REJECTED"; EXECUTING="EXECUTING"; COMPLETED="COMPLETED"

class SignalTransition(BaseModel):
    model_config=ConfigDict(frozen=True)
    from_state: SignalState; to_state: SignalState; occurred_at: datetime; reason: str; actor: str

class SignalRecord(BaseModel):
    model_config=ConfigDict(frozen=True)
    id: UUID=Field(default_factory=uuid4); asset: str; venue: str; direction: Direction
    created_at: datetime; expires_at: datetime; strategy_votes: tuple[StrategyVote,...]
    confidence: Decimal=Field(ge=0,le=1); provenance: tuple[str,...]=()

class SignalLifecycle(BaseModel):
    model_config=ConfigDict(frozen=True)
    signal_id: UUID; state: SignalState; version: int=Field(ge=1)
    updated_at: datetime; transitions: tuple[SignalTransition,...]

class SignalMonitoringSnapshot(BaseModel):
    model_config=ConfigDict(frozen=True)
    observed_at: datetime
    total_signals: int=Field(ge=0); active_signals: int=Field(ge=0)
    expired_signals: int=Field(ge=0); invalidated_signals: int=Field(ge=0)
    approved_signals: int=Field(ge=0); rejected_signals: int=Field(ge=0)
    completed_signals: int=Field(ge=0); mean_confidence: Decimal=Field(ge=0,le=1)
    stale_signal_count: int=Field(ge=0); alerts: tuple[str,...]=()
