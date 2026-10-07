from .contracts import Candle, DataQuality


class DownstreamDataGateError(RuntimeError):
    """Raised when an intelligence component receives unverified market data."""


def require_verified(candles: list[Candle] | tuple[Candle, ...]) -> tuple[Candle, ...]:
    if not candles:
        raise DownstreamDataGateError("downstream processing blocked: no verified market data")
    if any(candle.quality is not DataQuality.VERIFIED for candle in candles):
        raise DownstreamDataGateError(
            "downstream processing blocked: market data quality is not VERIFIED"
        )
    if any(not candle.checksum for candle in candles):
        raise DownstreamDataGateError(
            "downstream processing blocked: observation checksum is missing"
        )
    return tuple(candles)
