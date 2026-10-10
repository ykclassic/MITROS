from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field
from contracts.domain import Direction

class RiskDisposition(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class OpenPosition(BaseModel):
    model_config = ConfigDict(frozen=True)
    asset: str = Field(min_length=1)
    notional: Decimal = Field(ge=0)
    correlated_group: str = Field(min_length=1)
    direction: Direction

class RiskPolicy(BaseModel):
    """Immutable, independently supplied hard risk limits."""
    model_config = ConfigDict(frozen=True)
    max_risk_per_trade: Decimal = Field(gt=0, le=1)
    max_position_fraction: Decimal = Field(gt=0, le=1)
    max_gross_exposure_fraction: Decimal = Field(gt=0)
    max_daily_loss_fraction: Decimal = Field(gt=0, le=1)
    max_drawdown_fraction: Decimal = Field(gt=0, le=1)
    max_asset_concentration_fraction: Decimal = Field(gt=0, le=1)
    max_correlated_positions: int = Field(ge=1)
    max_correlated_exposure_fraction: Decimal = Field(gt=0)
    max_open_positions: int = Field(ge=1)
    min_risk_reward: Decimal = Field(gt=0)
    max_spread_fraction: Decimal = Field(ge=0, lt=1)
    max_slippage_fraction: Decimal = Field(ge=0, lt=1)
    min_data_quality: Decimal = Field(ge=0, le=1)
    max_quote_age_seconds: int = Field(gt=0)

class RiskEvaluationRequest(BaseModel):
    """Timestamped proposal and portfolio snapshot; not an execution command."""
    model_config = ConfigDict(frozen=True)
    proposal_id: str = Field(min_length=1)
    asset: str = Field(min_length=1)
    correlated_group: str = Field(min_length=1)
    direction: Direction
    as_of: datetime
    quote_observed_at: datetime
    data_verified: bool
    data_quality: Decimal = Field(ge=0, le=1)
    equity: Decimal = Field(gt=0)
    daily_pnl: Decimal
    peak_equity: Decimal = Field(gt=0)
    open_positions: tuple[OpenPosition, ...] = ()
    requested_notional: Decimal = Field(gt=0)
    entry: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    spread_fraction: Decimal = Field(ge=0)
    expected_slippage_fraction: Decimal = Field(ge=0)

class RiskCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    passed: bool
    observed: Decimal | str | bool
    threshold: Decimal | str | bool
    reason: str

class RiskDecisionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    proposal_id: str
    disposition: RiskDisposition
    approved_notional: Decimal = Field(ge=0)
    risk_amount: Decimal = Field(ge=0)
    risk_fraction: Decimal = Field(ge=0)
    reward_risk_ratio: Decimal = Field(ge=0)
    checks: tuple[RiskCheckResult, ...]
    rejection_reasons: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    evaluated_at: datetime
    risk_engine_version: str
    execution_authorized: bool = False
