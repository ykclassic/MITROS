create table if not exists market_data_provider_routes(
    id uuid primary key default gen_random_uuid(),
    provider_id uuid not null references market_data_providers(id),
    role text not null check(role in ('PRIMARY','SECONDARY','EMERGENCY')),
    priority integer not null check(priority > 0),
    cross_validate boolean not null default false,
    supported_timeframes text[] not null default '{}',
    supported_venues text[] not null default '{}',
    authority_conditions jsonb not null default '{}',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    unique(provider_id)
);

create table if not exists market_data_observation_manifests(
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references assets(id),
    venue_id uuid not null references venues(id),
    timeframe text not null,
    request_id uuid,
    batch_checksum text not null,
    manifest jsonb not null,
    data_quality text not null,
    created_at timestamptz not null default now(),
    check(data_quality in ('VERIFIED','DEGRADED','STALE','INCOMPLETE','CONFLICTED','INVALID','UNAVAILABLE'))
);

alter table market_data_providers add column if not exists role text not null default 'SECONDARY';
alter table market_data_providers add column if not exists supported_timeframes text[] not null default '{}';
alter table market_data_providers add column if not exists supported_venues text[] not null default '{}';
alter table market_data_providers add column if not exists cross_validate boolean not null default false;
alter table market_data_providers add column if not exists authority_conditions jsonb not null default '{}';

create index if not exists idx_provider_routes_priority on market_data_provider_routes(priority, active);
create index if not exists idx_observation_manifest_lookup on market_data_observation_manifests(asset_id, venue_id, timeframe, created_at desc);

insert into assets(symbol, asset_class, canonical_symbol)
values ('BTC/USD','crypto','BTC/USD'), ('ETH/USD','crypto','ETH/USD'), ('SOL/USD','crypto','SOL/USD')
on conflict (asset_class, canonical_symbol) do nothing;

insert into venues(name, venue_type)
values ('spot','crypto_spot')
on conflict (name) do nothing;

insert into market_data_providers(
    provider_key, provider_version, priority, role, supported_timeframes,
    supported_venues, cross_validate, authority_conditions
)
values
    ('twelvedata','v1',1,'PRIMARY',ARRAY['1m','5m','15m','30m','1h','4h','1d'],ARRAY['spot'],true,'{"on":"request","fallback_on":["unavailable","invalid","stale","incomplete"]}'),
    ('finnhub','v1',2,'SECONDARY',ARRAY['1m','5m','15m','30m','1h','4h','1d'],ARRAY['spot'],false,'{"on":"failover"}'),
    ('alphavantage','v1',3,'EMERGENCY',ARRAY['1m','5m','15m','30m','1h'],ARRAY['spot'],false,'{"on":"emergency"}')
on conflict (provider_key) do update set
    provider_version=excluded.provider_version, priority=excluded.priority, role=excluded.role,
    supported_timeframes=excluded.supported_timeframes, supported_venues=excluded.supported_venues,
    cross_validate=excluded.cross_validate, authority_conditions=excluded.authority_conditions, active=true;

insert into market_data_symbol_mappings(provider_id, canonical_asset, provider_symbol)
select p.id, m.canonical_asset, m.provider_symbol
from market_data_providers p
join (values
    ('twelvedata','BTC/USD','BTC/USD'),('twelvedata','ETH/USD','ETH/USD'),('twelvedata','SOL/USD','SOL/USD'),
    ('finnhub','BTC/USD','BINANCE:BTCUSDT'),('finnhub','ETH/USD','BINANCE:ETHUSDT'),('finnhub','SOL/USD','BINANCE:SOLUSDT'),
    ('alphavantage','BTC/USD','BTC'),('alphavantage','ETH/USD','ETH'),('alphavantage','SOL/USD','SOL')
) as m(provider_key, canonical_asset, provider_symbol)
on m.provider_key=p.provider_key
on conflict (provider_id, canonical_asset) do update set provider_symbol=excluded.provider_symbol, active=true;

insert into market_data_provider_routes(
    provider_id, role, priority, cross_validate, supported_timeframes, supported_venues, authority_conditions
)
select id, role, priority, cross_validate, supported_timeframes, supported_venues, authority_conditions
from market_data_providers
on conflict (provider_id) do update set
    role=excluded.role, priority=excluded.priority, cross_validate=excluded.cross_validate,
    supported_timeframes=excluded.supported_timeframes, supported_venues=excluded.supported_venues,
    authority_conditions=excluded.authority_conditions, active=true;

alter table market_data_observation_manifests enable row level security;
