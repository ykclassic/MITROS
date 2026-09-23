from collections.abc import Sequence
from hashlib import sha256
from packages.market_data.contracts import Candle, DataQuality

def validate_dataset(candles: Sequence[Candle]) -> tuple[Candle, ...]:
    if not candles:
        raise ValueError("dataset must not be empty")
    ordered = tuple(sorted(candles, key=lambda c: c.open_time))
    first = ordered[0]
    if any(c.quality is not DataQuality.VERIFIED for c in ordered):
        raise ValueError("research dataset requires VERIFIED candles")
    if any(c.asset != first.asset or c.venue != first.venue or c.timeframe != first.timeframe for c in ordered):
        raise ValueError("dataset must contain one asset, venue and timeframe")
    if any(b.open_time <= a.open_time for a, b in zip(ordered, ordered[1:])):
        raise ValueError("dataset timestamps must be strictly increasing")
    if any(c.close_time <= c.open_time for c in ordered):
        raise ValueError("candle close_time must follow open_time")
    return ordered

def dataset_checksum(candles: Sequence[Candle]) -> str:
    ordered = validate_dataset(candles)
    canonical = "|".join(c.model_dump_json(sort_keys=True) for c in ordered)
    return sha256(canonical.encode("utf-8")).hexdigest()
