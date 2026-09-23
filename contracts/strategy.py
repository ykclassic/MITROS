from collections.abc import Sequence
from typing import Protocol

from contracts.domain import StrategyVote
from contracts.features import FeatureSnapshot
from packages.market_data.contracts import Candle

class StrategyContext(Protocol):
    candles: Sequence[Candle]
    features: FeatureSnapshot

class Strategy(Protocol):
    strategy_id: str
    strategy_version: str

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        ...
