from collections.abc import Sequence
from hashlib import sha256
from packages.features.engine import FeatureEngine
from packages.strategies.base import StrategyContext, StrategyPlugin
from contracts.backtest import ReplayFrame, ReplayResult
from packages.market_data.contracts import Candle
from .dataset import dataset_checksum, validate_dataset

class ReplayEngine:
    """Deterministic historical replay with no live-state mutation."""
    def __init__(self, feature_engine: FeatureEngine | None = None) -> None:
        self.feature_engine = feature_engine or FeatureEngine()

    def run(self, candles: Sequence[Candle], strategy: StrategyPlugin) -> ReplayResult:
        data = validate_dataset(candles)
        frames: list[ReplayFrame] = []
        for i in range(49, len(data)):
            history = data[: i + 1]
            features = self.feature_engine.snapshot(history)
            vote = strategy.evaluate(StrategyContext(candles=history, features=features))
            feature_checksum = sha256(features.model_dump_json(sort_keys=True).encode()).hexdigest()
            frames.append(ReplayFrame(
                index=i, as_of=data[i].close_time, candles_seen=i + 1,
                feature_checksum=feature_checksum,
                direction=vote.direction.value if vote.direction else None,
                confidence=vote.confidence,
            ))
        return ReplayResult(
            dataset_checksum=dataset_checksum(data), frames=tuple(frames),
            frame_count=len(frames), provenance=("causal_replay", "verified_market_data_only"),
        )
