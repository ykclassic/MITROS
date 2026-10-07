from dataclasses import dataclass
from typing import Protocol

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
