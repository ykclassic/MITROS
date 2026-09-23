from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Sequence

IndicatorResult = Decimal | None
IndicatorFunction = Callable[[Sequence[Decimal]], IndicatorResult]

@dataclass(frozen=True, slots=True)
class FeatureSet:
    key: str
    version: str
    indicators: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class FeatureEngineConfig:
    feature_set: FeatureSet
    sma_period: int = 20
    ema_fast_period: int = 12
    ema_slow_period: int = 26
    macd_signal_period: int = 9
    rsi_period: int = 14
    atr_period: int = 14
    bollinger_period: int = 20
    bollinger_stddevs: Decimal = Decimal("2")
    minimum_history: int = 50
