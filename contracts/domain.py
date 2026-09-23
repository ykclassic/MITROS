from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
class Direction(StrEnum): LONG="LONG"; SHORT="SHORT"
class RiskDecision(StrEnum): APPROVED="APPROVED"; REJECTED="REJECTED"
class ApprovalStatus(StrEnum): PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"; EXPIRED="EXPIRED"
class ExecutionStatus(StrEnum):
    NOT_AUTHORIZED="NOT_AUTHORIZED"; AUTHORIZED="AUTHORIZED"; SUBMITTING="SUBMITTING"; SUBMITTED="SUBMITTED"
    PARTIALLY_FILLED="PARTIALLY_FILLED"; FILLED="FILLED"; CANCELLED="CANCELLED"; REJECTED="REJECTED"; UNKNOWN="UNKNOWN"
class Provenance(BaseModel):
    model_config=ConfigDict(frozen=True)
    source:str; source_version:str|None=None; observed_at:datetime; received_at:datetime; request_id:UUID|None=None; checksum:str|None=None
class Evidence(BaseModel):
    model_config=ConfigDict(frozen=True)
    kind:str; reference:str; value:str|None=None; provenance:Provenance
class StrategyVote(BaseModel):
    model_config=ConfigDict(frozen=True)
    strategy_id:str; strategy_version:str; direction:Direction|None; confidence:Decimal=Field(ge=0,le=1); reasons:tuple[str,...]=()
class RiskDecisionRecord(BaseModel):
    model_config=ConfigDict(frozen=True)
    decision:RiskDecision; reasons:tuple[str,...]; evaluated_at:datetime; risk_engine_version:str
class TradeProposal(BaseModel):
    model_config=ConfigDict(frozen=True)
    id:UUID=Field(default_factory=uuid4); asset:str; venue:str; direction:Direction; created_at:datetime; expires_at:datetime
    entry:Decimal; stop:Decimal; target:Decimal; risk_reward:Decimal=Field(gt=0); position_size:Decimal=Field(gt=0)
    strategy_votes:tuple[StrategyVote,...]; mtf_alignment:Decimal=Field(ge=0,le=1); regime:str
    sentiment:Decimal|None=Field(default=None,ge=-1,le=1); model_versions:tuple[str,...]=()
    data_quality:Decimal=Field(ge=0,le=1); evidence:tuple[Evidence,...]; risk:RiskDecisionRecord
    approval_status:ApprovalStatus=ApprovalStatus.PENDING; approval_actor:str|None=None; approval_at:datetime|None=None
    execution_status:ExecutionStatus=ExecutionStatus.NOT_AUTHORIZED; provenance:tuple[Provenance,...]
