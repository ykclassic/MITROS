from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ResearchArtifactType(StrEnum):
    DATASET = "DATASET"
    BACKTEST = "BACKTEST"
    WALK_FORWARD = "WALK_FORWARD"
    REPLAY = "REPLAY"
    ANALYSIS = "ANALYSIS"


class ResearchArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    artifact_type: ResearchArtifactType
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    checksum: str = Field(min_length=64, max_length=64)
    created_at: datetime
    metadata: dict[str, str] = {}


class ResearchQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: UUID = Field(default_factory=uuid4)
    asset: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    start: datetime
    end: datetime
    strategy_ids: tuple[str, ...] = ()
    artifact_ids: tuple[UUID, ...] = ()


class ResearchMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    value: Decimal
    sample_size: int = Field(ge=0)


class ResearchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: ResearchQuery
    artifacts: tuple[ResearchArtifact, ...] = ()
    metrics: tuple[ResearchMetric, ...] = ()
    findings: tuple[str, ...] = ()
    generated_at: datetime
