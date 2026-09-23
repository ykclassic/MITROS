from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    actor: str = Field(min_length=1)
    decision: ApprovalDecision
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    decided_at: datetime
    approval_token: str | None = None


class ApprovalOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: UUID
    decision: ApprovalDecision
    approval: ApprovalRecord
    execution_authorized: bool
