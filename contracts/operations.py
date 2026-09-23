from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class OperationalMode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class ReadinessStatus(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ReadinessCheck(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(min_length=1)
    status: CheckStatus
    detail: str = Field(min_length=1)


class ReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: ReadinessStatus
    checks: tuple[ReadinessCheck, ...]
