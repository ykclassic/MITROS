import asyncio

from packages.market_data.cache import AsyncTTLCache


def test_cache_coalesces_concurrent_loads() -> None:
    async def scenario() -> tuple[int, list[int], list[int]]:
        cache: AsyncTTLCache[list[int]] = AsyncTTLCache(ttl_seconds=60, max_entries=4)
        calls = 0

        async def loader() -> list[int]:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return [42]

        values = await asyncio.gather(
            cache.get_or_load("btc-1h", loader),
            cache.get_or_load("btc-1h", loader),
            cache.get_or_load("btc-1h", loader),
        )
        return calls, values[0], values[1]

    calls, first, second = asyncio.run(scenario())
    assert calls == 1
    assert first == [42]
    assert second == [42]
