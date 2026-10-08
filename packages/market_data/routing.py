from dataclasses import dataclass
from typing import Protocol, cast

import httpx
import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class ProviderRoute:
    provider_key: str
    provider_version: str
    priority: int
    role: str
    active: bool
    cross_validate: bool
    supported_timeframes: tuple[str, ...]
    supported_venues: tuple[str, ...]


class ProviderConfiguration(Protocol):
    async def routes(self, *, asset: str, venue: str, timeframe: str) -> tuple[ProviderRoute, ...]:
        ...


class StaticProviderConfiguration:
    def __init__(self, routes: tuple[ProviderRoute, ...]) -> None:
        self._routes = routes

    async def routes(self, *, asset: str, venue: str, timeframe: str) -> tuple[ProviderRoute, ...]:
        return tuple(
            route
            for route in sorted(self._routes, key=lambda item: item.priority)
            if route.active
            and (not route.supported_timeframes or timeframe in route.supported_timeframes)
            and (not route.supported_venues or venue in route.supported_venues)
        )


class SupabaseRestProviderConfiguration:
    """Loads provider authority from the MITROS Postgres tables through Supabase Data API."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        if not supabase_url or not service_role_key:
            raise ValueError("supabase_url and service_role_key are required")
        self.base_url = supabase_url.rstrip("/") + "/rest/v1"
        self.service_role_key = service_role_key

    async def _get(self, table: str, params: dict[str, str]) -> list[dict[str, object]]:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/{table}", params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise TypeError(f"Supabase returned a non-list payload for {table}")
        return [cast(dict[str, object], item) for item in payload if isinstance(item, dict)]

    async def routes(self, *, asset: str, venue: str, timeframe: str) -> tuple[ProviderRoute, ...]:
        providers = await self._get(
            "market_data_providers",
            {"select": "id,provider_key,provider_version", "active": "eq.true"},
        )
        mappings = await self._get(
            "market_data_symbol_mappings",
            {
                "select": "provider_id",
                "canonical_asset": f"eq.{asset}",
                "active": "eq.true",
            },
        )
        routes = await self._get(
            "market_data_provider_routes",
            {
                "select": "provider_id,priority,role,active,cross_validate,supported_timeframes,supported_venues",
                "active": "eq.true",
            },
        )
        provider_by_id = {str(item["id"]): item for item in providers if "id" in item}
        mapped_provider_ids = {str(item["provider_id"]) for item in mappings if "provider_id" in item}
        result: list[ProviderRoute] = []
        for row in routes:
            provider_id = str(row.get("provider_id", ""))
            provider = provider_by_id.get(provider_id)
            if provider is None or provider_id not in mapped_provider_ids:
                continue
            raw_timeframes = row.get("supported_timeframes")
            raw_venues = row.get("supported_venues")
            supported_timeframes = (
                tuple(str(item) for item in raw_timeframes)
                if isinstance(raw_timeframes, list)
                else ()
            )
            supported_venues = (
                tuple(str(item) for item in raw_venues)
                if isinstance(raw_venues, list)
                else ()
            )
            if supported_timeframes and timeframe not in supported_timeframes:
                continue
            if supported_venues and venue not in supported_venues:
                continue
            priority_raw = row.get("priority")
            priority = int(priority_raw) if isinstance(priority_raw, (int, str)) else 0
            result.append(
                ProviderRoute(
                    provider_key=str(provider["provider_key"]),
                    provider_version=str(provider["provider_version"]),
                    priority=priority,
                    role=str(row["role"]),
                    active=bool(row["active"]),
                    cross_validate=bool(row["cross_validate"]),
                    supported_timeframes=supported_timeframes,
                    supported_venues=supported_venues,
                )
            )
        return tuple(sorted(result, key=lambda item: item.priority))


class PostgresProviderConfiguration:
    """Loads provider authority and priority from MITROS Postgres."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url

    async def routes(self, *, asset: str, venue: str, timeframe: str) -> tuple[ProviderRoute, ...]:
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
                await cursor.execute(
                    """
                    select p.provider_key, p.provider_version,
                           r.priority, r.role, r.active, r.cross_validate,
                           r.supported_timeframes, r.supported_venues
                    from market_data_provider_routes r
                    join market_data_providers p on p.id = r.provider_id
                    join market_data_symbol_mappings m on m.provider_id = p.id
                    where m.canonical_asset = %s
                      and m.active = true
                      and r.active = true
                      and p.active = true
                      and (%s = any(r.supported_timeframes) or cardinality(r.supported_timeframes) = 0)
                      and (%s = any(r.supported_venues) or cardinality(r.supported_venues) = 0)
                    order by r.priority asc
                    """,
                    (asset, timeframe, venue),
                )
                rows = await cursor.fetchall()
        return tuple(
            ProviderRoute(
                provider_key=str(row["provider_key"]),
                provider_version=str(row["provider_version"]),
                priority=int(row["priority"]),
                role=str(row["role"]),
                active=bool(row["active"]),
                cross_validate=bool(row["cross_validate"]),
                supported_timeframes=tuple(row["supported_timeframes"] or ()),
                supported_venues=tuple(row["supported_venues"] or ()),
            )
            for row in rows
        )
