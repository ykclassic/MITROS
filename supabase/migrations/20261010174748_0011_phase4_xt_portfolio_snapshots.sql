create table if not exists phase4_portfolio_snapshots (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    venue text not null,
    account_type text not null,
    snapshot_at timestamptz not null,
    equity numeric not null check (equity > 0),
    daily_pnl numeric not null,
    peak_equity numeric not null check (peak_equity > 0),
    btc_usdt_price numeric not null check (btc_usdt_price > 0),
    balances jsonb not null,
    positions jsonb not null,
    created_at timestamptz not null default now()
);
create index if not exists idx_phase4_portfolio_snapshots_user_time
    on phase4_portfolio_snapshots(user_id, snapshot_at desc);
create index if not exists idx_phase4_portfolio_snapshots_user_peak
    on phase4_portfolio_snapshots(user_id, peak_equity desc);
alter table phase4_portfolio_snapshots enable row level security;
revoke all on table phase4_portfolio_snapshots from anon, authenticated;
grant all on table phase4_portfolio_snapshots to service_role;
