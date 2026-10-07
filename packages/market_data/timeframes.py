from datetime import timedelta

_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def timeframe_delta(timeframe: str) -> timedelta:
    try:
        return timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
    except KeyError as exc:
        raise ValueError(f"Unsupported canonical timeframe: {timeframe}") from exc
