from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .contracts import (
    Candle,
    DataQuality,
    ObservationManifestEntry,
    ProvenanceRecord,
)


class VerifiedMarketDataPersistenceError(RuntimeError):
    """Raised when verified data cannot be durably persisted."""


class PostgresVerifiedMarketDataRepository:
    """Durably stores verified observations and their provenance manifest."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url

    async def persist_candles(
        self,
        candles: Sequence[Candle],
        *,
        batch_checksum: str,
        manifest: Sequence[ObservationManifestEntry],
    ) -> tuple[UUID, ...]:
        if not candles or any(
            candle.quality is not DataQuality.VERIFIED for candle in candles
        ):
            raise VerifiedMarketDataPersistenceError(
                "only VERIFIED candles may be persisted"
            )

        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
                ids: list[UUID] = []
                identity: dict[str, UUID] | None = None

                for candle in candles:
                    await cursor.execute(
                        """
                        select a.id as asset_id, v.id as venue_id
                        from assets a cross join venues v
                        where a.canonical_symbol = %s
                          and v.name = %s
                          and a.active = true
                          and v.active = true
                        """,
                        (candle.asset, candle.venue),
                    )
                    identity = await cursor.fetchone()
                    if identity is None:
                        raise VerifiedMarketDataPersistenceError(
                            "canonical asset/venue not configured: "
                            f"{candle.asset}/{candle.venue}"
                        )

                    await cursor.execute(
                        """
                        insert into candles (
                            asset_id, venue_id, timeframe, open_time, close_time,
                            open, high, low, close, volume, provenance,
                            data_quality, request_id, checksum
                        )
                        values (
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,
                            'VERIFIED',%s,%s
                        )
                        on conflict (asset_id, venue_id, timeframe, open_time)
                        do update set
                            close_time=excluded.close_time,
                            open=excluded.open,
                            high=excluded.high,
                            low=excluded.low,
                            close=excluded.close,
                            volume=excluded.volume,
                            provenance=excluded.provenance,
                            data_quality=excluded.data_quality,
                            request_id=excluded.request_id,
                            checksum=excluded.checksum
                        returning id
                        """,
                        (
                            identity["asset_id"],
                            identity["venue_id"],
                            candle.timeframe,
                            candle.open_time,
                            candle.close_time,
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            json.dumps(
                                {
                                    "provider": candle.provider,
                                    "provider_version": candle.provider_version,
                                    "symbol": candle.symbol,
                                    "observed_at": candle.observed_at.isoformat(),
                                    "received_at": candle.received_at.isoformat(),
                                    "request_id": (
                                        str(candle.request_id)
                                        if candle.request_id
                                        else None
                                    ),
                                    "observation_checksum": candle.checksum,
                                    "batch_checksum": batch_checksum,
                                }
                            ),
                            candle.request_id,
                            candle.checksum,
                        ),
                    )
                    row = await cursor.fetchone()
                    if row is None:
                        raise VerifiedMarketDataPersistenceError(
                            "candle persistence did not return an observation id"
                        )
                    ids.append(row["id"])

                if identity is None:
                    raise VerifiedMarketDataPersistenceError(
                        "no canonical identity resolved"
                    )

                await cursor.execute(
                    """
                    insert into market_data_observation_manifests (
                        asset_id, venue_id, timeframe, request_id, batch_checksum,
                        manifest, data_quality
                    )
                    values (%s,%s,%s,%s,%s,%s::jsonb,'VERIFIED')
                    """,
                    (
                        identity["asset_id"],
                        identity["venue_id"],
                        candles[0].timeframe,
                        candles[0].request_id,
                        batch_checksum,
                        json.dumps(
                            [item.model_dump(mode="json") for item in manifest]
                        ),
                    ),
                )
                await cursor.execute(
                    """
                    insert into market_data (
                        asset_id, venue_id, timeframe, observed_at, received_at,
                        values, provenance, data_quality, request_id, checksum
                    )
                    values (
                        %s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                        'VERIFIED',%s,%s
                    )
                    """,
                    (
                        identity["asset_id"],
                        identity["venue_id"],
                        candles[0].timeframe,
                        candles[-1].observed_at,
                        candles[-1].received_at,
                        json.dumps(
                            {
                                "manifest": [
                                    item.model_dump(mode="json")
                                    for item in manifest
                                ]
                            }
                        ),
                        json.dumps({"batch_checksum": batch_checksum}),
                        candles[0].request_id,
                        batch_checksum,
                    ),
                )
            await connection.commit()
            return tuple(ids)

    async def reconstruct_provenance(
        self, observation_id: UUID
    ) -> ProvenanceRecord:
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    select c.id, a.canonical_symbol as asset, v.name as venue,
                           c.timeframe, c.provenance, c.data_quality
                    from candles c
                    join assets a on a.id = c.asset_id
                    join venues v on v.id = c.venue_id
                    where c.id = %s
                    """,
                    (observation_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise VerifiedMarketDataPersistenceError(
                        f"observation {observation_id} was not found"
                    )

                provenance = row["provenance"]
                return ProvenanceRecord(
                    observation_id=row["id"],
                    asset=row["asset"],
                    venue=row["venue"],
                    symbol=provenance["symbol"],
                    timeframe=row["timeframe"],
                    provider=provenance["provider"],
                    provider_version=provenance.get("provider_version"),
                    request_id=(
                        UUID(provenance["request_id"])
                        if provenance.get("request_id")
                        else None
                    ),
                    observation_checksum=provenance["observation_checksum"],
                    batch_checksum=provenance.get("batch_checksum"),
                    data_quality=DataQuality(row["data_quality"]),
                    observed_at=datetime.fromisoformat(
                        provenance["observed_at"]
                    ),
                    received_at=datetime.fromisoformat(
                        provenance["received_at"]
                    ),
                )
