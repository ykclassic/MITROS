from collections.abc import Sequence
from decimal import Decimal
from packages.market_data.contracts import Candle
from packages.strategies.base import StrategyPlugin
from contracts.backtest import BacktestConfig, WalkForwardFold, WalkForwardResult
from .backtest import BacktestEngine
from .dataset import dataset_checksum, validate_dataset

class WalkForwardEngine:
    """Expanding-window walk-forward evaluator with an explicit purge gap."""
    def __init__(self, backtester: BacktestEngine | None = None) -> None:
        self.backtester = backtester or BacktestEngine()

    def evaluate(self, candles: Sequence[Candle], strategy: StrategyPlugin, config: BacktestConfig,
                 train_bars: int, test_bars: int, step_bars: int, purge_bars: int) -> WalkForwardResult:
        data = validate_dataset(candles)
        if min(train_bars, test_bars, step_bars) <= 0 or purge_bars < 0:
            raise ValueError("window sizes must be positive and purge must be nonnegative")
        if train_bars < 51:
            raise ValueError("train_bars must be at least 51")
        folds: list[WalkForwardFold] = []
        results = []
        fold, train_end = 1, train_bars
        while train_end + purge_bars + test_bars <= len(data):
            test_start, test_end = train_end + purge_bars, train_end + purge_bars + test_bars
            combined = data[:test_end]
            train, test = data[:train_end], data[test_start:test_end]
            folds.append(WalkForwardFold(
                fold=fold, train_start=train[0].open_time, train_end=train[-1].close_time,
                test_start=test[0].open_time, test_end=test[-1].close_time,
                purge_bars=purge_bars, train_size=len(train), test_size=len(test),
            ))
            results.append(self.backtester.run(combined, strategy, config, evaluation_start=test_start))
            fold += 1
            train_end += step_bars
        if not results:
            raise ValueError("dataset does not contain a complete walk-forward fold")
        return WalkForwardResult(
            dataset_checksum=dataset_checksum(data), folds=tuple(folds), oos_results=tuple(results),
            aggregate_oos_return=sum((r.total_return for r in results), start=Decimal("0")),
            aggregate_oos_max_drawdown=max((r.max_drawdown for r in results), default=Decimal("0")),
            provenance=("expanding_train_window", "explicit_purge_gap", "purged_out_of_sample_evaluation"),
        )
