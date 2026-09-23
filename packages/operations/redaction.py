from collections.abc import Mapping
from typing import Any

_SENSITIVE = frozenset({
    "authorization", "password", "secret", "token", "api_key", "apikey",
    "private_key", "access_token", "refresh_token",
})


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        normalized = key.lower().replace("-", "_")
        if normalized in _SENSITIVE or any(
            part in normalized for part in ("password", "secret", "token")
        ):
            result[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            result[key] = redact_mapping(value)
        else:
            result[key] = value
    return result
