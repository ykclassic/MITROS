create table if not exists intelligence_snapshots (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references assets(id),
    venue_id uuid not null references venues(id),
    timeframe text not null,
    as_of timestamptz not null,
    snapshot_checksum text not null,
    input_checksums text[] not null,
    engine_version text not null,
    configuration_version text not null,
    observation_window jsonb not null,
    payload jsonb not null,
    provenance jsonb not null,
    created_at timestamptz not null default now(),
    unique(asset_id, venue_id, timeframe, snapshot_checksum)
);

create index if not exists idx_intelligence_snapshots_lookup
    on intelligence_snapshots(asset_id, venue_id, timeframe, as_of desc);

alter table intelligence_snapshots enable row level security;
revoke all on table intelligence_snapshots from anon, authenticated;
grant all on table intelligence_snapshots to service_role;
