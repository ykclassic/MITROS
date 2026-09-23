from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RiskCheck(StrEnum):
    EXPOSURE = "EXPOSURE"
    POSITION_SIZE = "POSITION_SIZE"
    DAILY_LOSS = "DAILY_LOSS"
    CONCENTRATION = "CONCENTRATION"
    CORRELATION = "CORRELATION"
    LEVERAGE = "LEVERAGE"
    DRAWDOWN = "DRAWDOWN"
    SPREAD = "SPREAD"


class PositionState(BaseModel):
    model_config = ConfigDict(frozen=True)
    asset: str
    market_value: Decimal = Field(ge=0)
    unrealized_pnl: Decimal
    direction: str


class PortfolioState(BaseModel):
    model_config = ConfigDict(frozen=True)
    equity: Decimal = Field(gt=0)
    balance: Decimal = Field(gt=0)
    daily_pnl: Decimal
    peak_equity: Decimal = Field(gt=0)
    positions: tuple[PositionState, ...] = ()

    @property
    def drawdown(self) -> Decimal:
        return max(Decimal("0"), (self.peak_equity - self.equity) / self.peak_equity)

    @property
    def gross_exposure(self) -> Decimal:
        return sum((p.market_value for p in self.positions), Decimal("0")) / self.equity


class RiskLimits(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_position_fraction: Decimal = Field(gt=0, le=1)
    max_gross_exposure: Decimal = Field(gt=0)
    max_daily_loss_fraction: Decimal = Field(gt=0, le=1)
    max_drawdown_fraction: Decimal = Field(gt=0, le=1)
    max_concentration_fraction: Decimal = Field(gt=0, le=1)
    max_leverage: Decimal = Field(gt=0)
    max_spread_fraction: Decimal = Field(gt=0, le=1)


class RiskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)
    approved: bool
    requested_size: Decimal = Field(gt=0)
    approved_size: Decimal = Field(ge=0)
    checks: tuple[RiskCheck, ...]
    reasons: tuple[str, ...]
    risk_score: Decimal = Field(ge=0, le=1)
