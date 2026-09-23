"""Deterministic, research-only backtesting, walk-forward and replay components."""
from .backtest import BacktestEngine
from .dataset import VerifiedDataset
from .metrics import max_drawdown, win_rate
from .platform import ResearchPlatform
from .replay import ReplayEngine
from .walk_forward import WalkForwardEngine

__all__ = [
    "BacktestEngine",
    "ReplayEngine",
    "ResearchPlatform",
    "VerifiedDataset",
    "WalkForwardEngine",
    "max_drawdown",
    "win_rate",
]
