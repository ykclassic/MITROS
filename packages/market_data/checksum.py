import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any


def canonical_checksum(value: Mapping[str, Any] | Sequence[Any]) -> str:
    def default(item: Any) -> str:
        if isinstance(item, Decimal):
            return format(item, "f")
        raise TypeError(f"Unsupported checksum value: {type(item)!r}")

    payload = json.dumps(
        value,
        default=default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
