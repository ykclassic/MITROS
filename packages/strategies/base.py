from collections.abc import Sequence
from dataclasses import dataclass

from contracts.domain import StrategyVote
from contracts.features import FeatureSnapshot
from packages.market_data.contracts import Candle

@dataclass(frozen=True, slots=True)
class StrategyContext:
    candles: Sequence[Candle]
    features: FeatureSnapshot

class StrategyPlugin:
    strategy_id: str = "base"
    strategy_version: str = "0.0.0"

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        raise NotImplementedError
