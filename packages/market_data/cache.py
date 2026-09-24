from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class _Entry[T]:
    value: T
    expires_at: float


class AsyncTTLCache[T]:
    """Small process-local cache with per-key in-flight request coalescing."""

    def __init__(self, *, ttl_seconds: float = 30.0, max_entries: int = 64) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, _Entry[T]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at > now:
            return entry.value

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value

            value = await loader()
            self._entries[key] = _Entry(value=value, expires_at=time.monotonic() + self.ttl_seconds)
            self._evict()
            return value

    def clear(self) -> None:
        self._entries.clear()

    def _evict(self) -> None:
        if len(self._entries) <= self.max_entries:
            return
        oldest = min(self._entries, key=lambda key: self._entries[key].expires_at)
        self._entries.pop(oldest, None)
