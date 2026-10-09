from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
import psycopg
from psycopg.rows import dict_row

from .contracts import Candle, DataQuality, ObservationManifestEntry, ProvenanceRecord


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
        if not candles or any(candle.quality is not DataQuality.VERIFIED for candle in candles):
            raise VerifiedMarketDataPersistenceError(
                "only VERIFIED candles may be persisted"
            )

        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
            ids: list[UUID] = []
            identity: dict[str, Any] | None = None

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
                on conflict (asset_id, venue_id, timeframe, observed_at)
                do update set received_at=excluded.received_at, values=excluded.values,
                    provenance=excluded.provenance, data_quality=excluded.data_quality,
                    request_id=excluded.request_id, checksum=excluded.checksum
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
        ) as connection, connection.cursor() as cursor:
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
                observed_at=datetime.fromisoformat(provenance["observed_at"]),
                received_at=datetime.fromisoformat(provenance["received_at"]),
            )



    async def persist_intelligence(
        self, *, asset: str, venue: str, timeframe: str, snapshot: Any,
        features: Any, strategy_votes: Sequence[Any], mtf: Any, batch_checksum: str,
    ) -> None:
        provenance = {
            "data_quality": "VERIFIED",
            "batch_checksum": batch_checksum,
            "input_checksums": list(snapshot.input_checksums),
            "observation_window": [value.isoformat() for value in snapshot.observation_window],
            "engine_version": snapshot.engine_version,
            "configuration_version": snapshot.configuration_version,
            "snapshot_checksum": snapshot.snapshot_checksum,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        values = {key: str(value) for key, value in features.values.items()}
        payload = {
            "quantitative": snapshot.quantitative.model_dump(mode="json"),
            "structure": snapshot.structure.model_dump(mode="json"),
            "liquidity": snapshot.liquidity.model_dump(mode="json"),
            "smc": snapshot.smc.model_dump(mode="json"),
            "crt": snapshot.crt.model_dump(mode="json"),
            "regime": snapshot.regime.model_dump(mode="json"),
            "features": values,
            "strategy_votes": [item.model_dump(mode="json") for item in strategy_votes],
            "mtf": mtf.model_dump(mode="json"),
        }
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """select a.id as asset_id, v.id as venue_id
                   from assets a cross join venues v
                   where a.canonical_symbol=%s and v.name=%s
                     and a.active=true and v.active=true""",
                (asset, venue),
            )
            identity = await cursor.fetchone()
            if identity is None:
                raise VerifiedMarketDataPersistenceError(
                    "canonical asset/venue reference is missing"
                )
            await cursor.execute(
                """insert into features
                   (asset_id,venue_id,timeframe,as_of,feature_set_version,values,provenance)
                   values (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)""",
                (identity["asset_id"], identity["venue_id"], timeframe, snapshot.as_of,
                 features.feature_set_version, json.dumps(values),
                 json.dumps(provenance)),
            )
            await cursor.execute(
                """insert into regimes
                   (asset_id,venue_id,as_of,regime,confidence,version,provenance)
                   values (%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (identity["asset_id"], identity["venue_id"], snapshot.as_of,
                 snapshot.regime.regime.value, snapshot.regime.confidence,
                 snapshot.regime.model_version, json.dumps(provenance)),
            )
            await cursor.execute(
                """insert into intelligence_snapshots
                   (asset_id,venue_id,timeframe,as_of,snapshot_checksum,input_checksums,
                    engine_version,configuration_version,observation_window,payload,provenance)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                   on conflict (asset_id,venue_id,timeframe,snapshot_checksum)
                   do update set payload=excluded.payload,provenance=excluded.provenance""",
                (identity["asset_id"], identity["venue_id"], timeframe, snapshot.as_of,
                 snapshot.snapshot_checksum, list(snapshot.input_checksums),
                 snapshot.engine_version, snapshot.configuration_version,
                 json.dumps(provenance["observation_window"]), json.dumps(payload, default=str),
                 json.dumps(provenance)),
            )
            await connection.commit()


class SupabaseRestVerifiedMarketDataRepository:
    """Supabase Data API implementation of the verified-observation repository."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        if not supabase_url.strip() or not service_role_key.strip():
            raise ValueError("Supabase URL and service-role credentials are required")
        self.base_url = supabase_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, table: str, *,
        params: dict[str, str] | None = None,
        payload: Any = None, prefer: str = "return=minimal",
    ) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method, f"{self.base_url}/{table}", params=params, json=payload,
                headers={**self._headers, "Prefer": prefer},
            )
        if response.is_error:
            raise VerifiedMarketDataPersistenceError(
                f"Supabase persistence failed for {table}: HTTP {response.status_code}"
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def _identity(self, asset: str, venue: str) -> tuple[str, str]:
        assets = await self._request(
            "GET", "assets",
            params={"select": "id", "canonical_symbol": f"eq.{asset}", "active": "eq.true", "limit": "1"},
        )
        venues = await self._request(
            "GET", "venues",
            params={"select": "id", "name": f"eq.{venue}", "active": "eq.true", "limit": "1"},
        )
        if not isinstance(assets, list) or not assets or not isinstance(venues, list) or not venues:
            raise VerifiedMarketDataPersistenceError("canonical asset/venue reference is missing")
        return str(assets[0]["id"]), str(venues[0]["id"])

    async def persist_candles(
        self, candles: Sequence[Candle], *, batch_checksum: str,
        manifest: Sequence[ObservationManifestEntry],
    ) -> tuple[UUID, ...]:
        if not candles or any(c.quality is not DataQuality.VERIFIED or not c.checksum for c in candles):
            raise VerifiedMarketDataPersistenceError("only checksummed VERIFIED candles may be persisted")
        asset_id, venue_id = await self._identity(candles[0].asset, candles[0].venue)
        rows = [{
            "asset_id": asset_id, "venue_id": venue_id, "timeframe": c.timeframe,
            "open_time": c.open_time.isoformat(), "close_time": c.close_time.isoformat(),
            "open": str(c.open), "high": str(c.high), "low": str(c.low), "close": str(c.close),
            "volume": str(c.volume) if c.volume is not None else None,
            "data_quality": "VERIFIED", "request_id": str(c.request_id) if c.request_id else None,
            "checksum": c.checksum,
            "provenance": {
                "provider": c.provider, "provider_version": c.provider_version,
                "symbol": c.symbol, "request_id": str(c.request_id) if c.request_id else None,
                "observation_checksum": c.checksum, "batch_checksum": batch_checksum,
                "observed_at": c.observed_at.isoformat(), "received_at": c.received_at.isoformat(),
            },
        } for c in candles]
        await self._request(
            "POST", "candles", params={"on_conflict": "asset_id,venue_id,timeframe,open_time"},
            payload=rows, prefer="resolution=merge-duplicates,return=minimal",
        )
        latest = candles[-1]
        await self._request(
            "POST", "market_data",
            params={"on_conflict": "asset_id,venue_id,timeframe,observed_at"},
            payload={
                "asset_id": asset_id, "venue_id": venue_id, "timeframe": latest.timeframe,
                "observed_at": latest.observed_at.isoformat(), "received_at": latest.received_at.isoformat(),
                "values": {"count": len(candles), "batch_checksum": batch_checksum},
                "provenance": {"batch_checksum": batch_checksum, "observation_count": len(candles)},
                "data_quality": "VERIFIED", "request_id": str(latest.request_id) if latest.request_id else None,
                "checksum": batch_checksum,
            },
        )
        await self._request(
            "POST", "market_data_observation_manifests",
            payload={
                "asset_id": asset_id, "venue_id": venue_id, "timeframe": latest.timeframe,
                "request_id": str(latest.request_id) if latest.request_id else None,
                "batch_checksum": batch_checksum,
                "manifest": [item.model_dump(mode="json") for item in manifest],
                "data_quality": "VERIFIED",
            },
        )
        return ()

    async def persist_intelligence(
        self, *, asset: str, venue: str, timeframe: str, snapshot: Any,
        features: Any, strategy_votes: Sequence[Any], mtf: Any, batch_checksum: str,
    ) -> None:
        asset_id, venue_id = await self._identity(asset, venue)
        as_of = snapshot.as_of.isoformat()
        provenance = {
            "data_quality": "VERIFIED", "batch_checksum": batch_checksum,
            "input_checksums": list(snapshot.input_checksums),
            "observation_window": [value.isoformat() for value in snapshot.observation_window],
            "engine_version": snapshot.engine_version,
            "configuration_version": snapshot.configuration_version,
            "snapshot_checksum": snapshot.snapshot_checksum,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        values = {key: str(value) for key, value in features.values.items()}
        await self._request("POST", "features", payload={
            "asset_id": asset_id, "venue_id": venue_id, "timeframe": timeframe,
            "as_of": as_of, "feature_set_version": features.feature_set_version,
            "values": values, "provenance": provenance,
        })
        await self._request("POST", "regimes", payload={
            "asset_id": asset_id, "venue_id": venue_id, "as_of": as_of,
            "regime": snapshot.regime.regime.value, "confidence": str(snapshot.regime.confidence),
            "version": snapshot.regime.model_version, "provenance": provenance,
        })
        await self._request(
            "POST", "intelligence_snapshots",
            params={"on_conflict": "asset_id,venue_id,timeframe,snapshot_checksum"},
            payload={
                "asset_id": asset_id, "venue_id": venue_id, "timeframe": timeframe,
                "as_of": as_of, "snapshot_checksum": snapshot.snapshot_checksum,
                "input_checksums": list(snapshot.input_checksums),
                "engine_version": snapshot.engine_version,
                "configuration_version": snapshot.configuration_version,
                "observation_window": provenance["observation_window"],
                "payload": {
                    "quantitative": snapshot.quantitative.model_dump(mode="json"),
                    "structure": snapshot.structure.model_dump(mode="json"),
                    "liquidity": snapshot.liquidity.model_dump(mode="json"),
                    "smc": snapshot.smc.model_dump(mode="json"),
                    "crt": snapshot.crt.model_dump(mode="json"),
                    "regime": snapshot.regime.model_dump(mode="json"),
                    "features": values,
                    "strategy_votes": [item.model_dump(mode="json") for item in strategy_votes],
                    "mtf": mtf.model_dump(mode="json"),
                },
                "provenance": provenance,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
