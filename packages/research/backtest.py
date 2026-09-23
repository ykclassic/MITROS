from collections.abc import Sequence
from decimal import Decimal
from hashlib import sha256
from packages.features.engine import FeatureEngine
from packages.strategies.base import StrategyContext, StrategyPlugin
from contracts.backtest import BacktestConfig, BacktestResult, BacktestTrade
from packages.market_data.contracts import Candle
from .dataset import dataset_checksum, validate_dataset
from .metrics import max_drawdown, win_rate

class BacktestEngine:
    """Causal next-bar research simulator. It has no execution capability."""
    def __init__(self, feature_engine: FeatureEngine | None = None) -> None:
        self.feature_engine = feature_engine or FeatureEngine()

    @staticmethod
    def _config_checksum(config: BacktestConfig) -> str:
        return sha256(config.model_dump_json(sort_keys=True).encode()).hexdigest()

    def run(self, candles: Sequence[Candle], strategy: StrategyPlugin, config: BacktestConfig,
            evaluation_start: int = 49) -> BacktestResult:
        data = validate_dataset(candles)
        if len(data) < 51:
            raise ValueError("backtest requires at least 51 verified candles")
        if not 49 <= evaluation_start < len(data) - 1:
            raise ValueError("evaluation_start must leave a feature warmup and next bar")
        if config.strategy_id != strategy.strategy_id or config.strategy_version != strategy.strategy_version:
            raise ValueError("strategy identity does not match backtest configuration")
        equity = config.initial_equity
        trades: list[BacktestTrade] = []
        curve: list[Decimal] = [equity]
        for i in range(evaluation_start, len(data) - 1):
            history = data[: i + 1]
            features = self.feature_engine.snapshot(history)
            vote = strategy.evaluate(StrategyContext(candles=history, features=features))
            if vote.direction is None or vote.confidence <= 0:
                curve.append(equity)
                continue
            bar = data[i + 1]
            entry, exit_price = bar.open, bar.close
            raw = (exit_price - entry) / entry
            gross = raw if vote.direction.value == "LONG" else -raw
            costs = config.commission_fraction + config.slippage_fraction
            net = gross * config.position_fraction - costs * config.position_fraction
            equity *= Decimal("1") + net
            trades.append(BacktestTrade(
                opened_at=bar.open_time, closed_at=bar.close_time,
                direction=vote.direction.value, entry=entry, exit=exit_price,
                gross_return=gross, costs=costs, net_return=net, equity_after=equity,
                signal_index=i,
            ))
            curve.append(equity)
        returns = [t.net_return for t in trades]
        return BacktestResult(
            dataset_checksum=dataset_checksum(data),
            config_checksum=self._config_checksum(config),
            trades=tuple(trades), initial_equity=config.initial_equity, final_equity=equity,
            total_return=(equity / config.initial_equity) - 1,
            max_drawdown=max_drawdown(curve, config.initial_equity),
            win_rate=win_rate(returns), trade_count=len(trades),
            provenance=("decision_at_completed_candle", "fill_at_next_bar_open", "next_bar_open_to_close"),
        )
