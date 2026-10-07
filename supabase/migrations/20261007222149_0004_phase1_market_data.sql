create table if not exists market_data_providers(
    id uuid primary key default gen_random_uuid(),
    provider_key text not null unique,
    provider_version text not null,
    priority integer not null check(priority > 0),
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists market_data_symbol_mappings(
    id uuid primary key default gen_random_uuid(),
    provider_id uuid not null references market_data_providers(id),
    canonical_asset text not null,
    provider_symbol text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    unique(provider_id, canonical_asset)
);

alter table candles add column if not exists data_quality text not null default 'VERIFIED';
alter table candles add column if not exists request_id uuid;
alter table candles add column if not exists checksum text;

alter table market_data add column if not exists request_id uuid;
alter table market_data add column if not exists checksum text;

do $$
begin
    alter table candles
        add constraint candles_data_quality_check
        check (data_quality in ('VERIFIED','DEGRADED','STALE','INCOMPLETE','CONFLICTED','INVALID','UNAVAILABLE'));
exception
    when duplicate_object then null;
end $$;

create index if not exists idx_candles_quality_lookup
    on candles(asset_id, venue_id, timeframe, data_quality, open_time desc);

create index if not exists idx_market_data_quality_lookup
    on market_data(asset_id, venue_id, timeframe, data_quality, observed_at desc);

create index if not exists idx_provider_mapping_lookup
    on market_data_symbol_mappings(provider_id, canonical_asset)
    where active = true;

alter table market_data_providers enable row level security;
alter table market_data_symbol_mappings enable row level security;
