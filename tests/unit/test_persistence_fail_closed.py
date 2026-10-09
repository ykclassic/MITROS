from packages.market_data.persistence import (
    PostgresVerifiedMarketDataRepository,
    SupabaseRestVerifiedMarketDataRepository,
    VerifiedMarketDataPersistenceError,
)


async def test_postgres_persistence_refuses_empty_batch_before_connecting() -> None:
    repository = PostgresVerifiedMarketDataRepository("postgresql://unused")
    try:
        await repository.persist_candles([], batch_checksum="abc", manifest=[])
    except VerifiedMarketDataPersistenceError as exc:
        assert "only VERIFIED candles" in str(exc)
    else:
        raise AssertionError("empty batch must fail closed")


async def test_supabase_persistence_refuses_empty_batch_before_network_io() -> None:
    repository = SupabaseRestVerifiedMarketDataRepository(
        "https://example.supabase.co", "not-a-real-key"
    )
    try:
        await repository.persist_candles([], batch_checksum="abc", manifest=[])
    except VerifiedMarketDataPersistenceError as exc:
        assert "only checksummed VERIFIED candles" in str(exc)
    else:
        raise AssertionError("empty batch must fail closed")


def test_supabase_persistence_requires_server_side_credentials() -> None:
    try:
        SupabaseRestVerifiedMarketDataRepository("", "")
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("missing credentials must be rejected")
