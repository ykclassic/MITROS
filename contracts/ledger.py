from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.execution.interface import ExecutionResult


class LedgerOrderState(StrEnum):
    INTENDED = "INTENDED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"


class ExecutionIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    client_order_id: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    asset: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    created_at: datetime


class LedgerEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    client_order_id: str
    proposal_id: UUID
    state: LedgerOrderState
    result: ExecutionResult | None = None
    recorded_at: datetime
    attempt: int = Field(ge=0)
    request_fingerprint: str = Field(min_length=1)


class ReconciliationStatus(StrEnum):
    MATCHED = "MATCHED"
    MISSING = "MISSING"
    DIVERGENT = "DIVERGENT"


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str
    status: ReconciliationStatus
    local: LedgerEntry
    remote: ExecutionResult | None
    reasons: tuple[str, ...] = ()
    reconciled_at: datetime
