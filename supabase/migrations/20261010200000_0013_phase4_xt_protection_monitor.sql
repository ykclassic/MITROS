create table if not exists phase4_protective_positions (
    proposal_id uuid primary key references trade_proposals(id),
    owner_user_id text not null,
    asset text not null,
    direction text not null check (direction in ('LONG', 'SHORT')),
    entry_quantity numeric not null check (entry_quantity > 0),
    stop_loss numeric not null check (stop_loss > 0),
    take_profit numeric not null check (take_profit > 0),
    status text not null check (status in ('ACTIVE', 'EXITING', 'CLOSED', 'FAILED')),
    entry_order_id text,
    exit_client_order_id text,
    exit_order_id text,
    exit_status text,
    exit_filled_quantity numeric not null default 0,
    triggered_reason text,
    last_price numeric,
    last_checked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_phase4_protective_positions_status
    on phase4_protective_positions(status, updated_at);
create index if not exists idx_phase4_protective_positions_owner
    on phase4_protective_positions(owner_user_id, created_at desc);
alter table phase4_protective_positions enable row level security;
revoke all on table phase4_protective_positions from anon, authenticated;
grant all on table phase4_protective_positions to service_role;
