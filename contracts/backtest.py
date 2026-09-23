from datetime import datetime
from enum import StrEnum
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class BacktestFillModel(StrEnum):
    NEXT_BAR_OPEN_TO_CLOSE = "NEXT_BAR_OPEN_TO_CLOSE"

class BacktestConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    initial_equity: Decimal = Field(gt=0)
    position_fraction: Decimal = Field(gt=0, le=1)
    commission_fraction: Decimal = Field(ge=0, le=1)
    slippage_fraction: Decimal = Field(ge=0, le=1)
    fill_model: BacktestFillModel = BacktestFillModel.NEXT_BAR_OPEN_TO_CLOSE
    seed: int = Field(ge=0)
    strategy_id: str
    strategy_version: str
    feature_set_version: str

class BacktestTrade(BaseModel):
    model_config = ConfigDict(frozen=True)
    opened_at: datetime
    closed_at: datetime
    direction: str
    entry: Decimal
    exit: Decimal
    gross_return: Decimal
    costs: Decimal
    net_return: Decimal
    equity_after: Decimal
    signal_index: int

class BacktestResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    dataset_checksum: str = Field(min_length=64, max_length=64)
    config_checksum: str = Field(min_length=64, max_length=64)
    trades: tuple[BacktestTrade, ...]
    initial_equity: Decimal = Field(gt=0)
    final_equity: Decimal = Field(gt=0)
    total_return: Decimal
    max_drawdown: Decimal = Field(ge=0)
    win_rate: Decimal = Field(ge=0, le=1)
    trade_count: int = Field(ge=0)
    provenance: tuple[str, ...] = ()

class WalkForwardFold(BaseModel):
    model_config = ConfigDict(frozen=True)
    fold: int = Field(ge=1)
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    purge_bars: int = Field(ge=0)
    train_size: int = Field(ge=1)
    test_size: int = Field(ge=1)

class WalkForwardResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    dataset_checksum: str = Field(min_length=64, max_length=64)
    folds: tuple[WalkForwardFold, ...]
    oos_results: tuple[BacktestResult, ...]
    aggregate_oos_return: Decimal
    aggregate_oos_max_drawdown: Decimal = Field(ge=0)
    provenance: tuple[str, ...] = ()

class ReplayFrame(BaseModel):
    model_config = ConfigDict(frozen=True)
    index: int = Field(ge=0)
    as_of: datetime
    candles_seen: int = Field(ge=1)
    feature_checksum: str = Field(min_length=64, max_length=64)
    direction: str | None
    confidence: Decimal = Field(ge=0, le=1)

class ReplayResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    dataset_checksum: str = Field(min_length=64, max_length=64)
    frames: tuple[ReplayFrame, ...]
    frame_count: int = Field(ge=0)
    provenance: tuple[str, ...] = ()
