from datetime import timedelta
from .contracts import Candle

def filter_completed_candles(candles:list[Candle],now,interval:timedelta)->list[Candle]:
    return [c for c in candles if c.close_time+interval<=now]

def validate_ohlcv(candle:Candle)->None:
    if candle.high < max(candle.open,candle.close) or candle.low > min(candle.open,candle.close):
        raise ValueError("Invalid OHLC relationship")
    if candle.high < candle.low: raise ValueError("High cannot be below low")
    if candle.volume is not None and candle.volume < 0: raise ValueError("Volume cannot be negative")
