from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelLifecycleStage(StrEnum):
    DEVELOPED = "DEVELOPED"
    VALIDATED = "VALIDATED"
    STAGED = "STAGED"
    PRODUCTION = "PRODUCTION"
    RETIRED = "RETIRED"


class ModelVersion(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_id: str
    version: str
    stage: ModelLifecycleStage
    feature_set_version: str
    artifact_checksum: str = Field(min_length=64, max_length=64)
    training_data_checksum: str = Field(min_length=64, max_length=64)
    created_at: datetime


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_id: str
    model_version: str
    sample_size: int = Field(ge=1)
    walk_forward_folds: int = Field(ge=1)
    purged_observations: int = Field(ge=0)
    mean_score: Decimal = Field(ge=0, le=1)
    minimum_score: Decimal = Field(ge=0, le=1)
    passed: bool
    evaluated_at: datetime
    reasons: tuple[str, ...] = ()


class ModelPrediction(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_id: str
    model_version: str
    prediction_id: UUID
    as_of: datetime
    probability: Decimal = Field(ge=0, le=1)
    direction: str
    feature_set_version: str
    feature_checksum: str = Field(min_length=64, max_length=64)
    provenance: tuple[str, ...] = ()


class DriftStatus(StrEnum):
    STABLE = "STABLE"
    WARNING = "WARNING"
    BREACHED = "BREACHED"


class DriftReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_id: str
    model_version: str
    feature_name: str
    baseline_mean: Decimal
    current_mean: Decimal
    relative_shift: Decimal = Field(ge=0)
    status: DriftStatus
    sample_size: int = Field(ge=1)
    evaluated_at: datetime
    reasons: tuple[str, ...] = ()
