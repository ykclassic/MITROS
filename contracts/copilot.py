from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvidenceKind(StrEnum):
    DATASET = "DATASET"
    BACKTEST = "BACKTEST"
    WALK_FORWARD = "WALK_FORWARD"
    REPLAY = "REPLAY"
    REPORT = "REPORT"


class ResearchEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: UUID = Field(default_factory=uuid4)
    kind: EvidenceKind
    artifact_id: UUID
    title: str = Field(min_length=1)
    checksum: str = Field(min_length=64, max_length=64)
    excerpt: str = ""
    source_timestamp: datetime | None = None


class ResearchAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: UUID
    answer: str = Field(min_length=1)
    evidence: tuple[ResearchEvidence, ...]
    grounded: bool
    generated_at: datetime
