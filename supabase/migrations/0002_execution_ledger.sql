create table if not exists execution_intents(
  id uuid primary key default gen_random_uuid(),
  proposal_id uuid not null references trade_proposals(id),
  client_order_id text not null unique,
  venue_id uuid not null references venues(id),
  asset_id uuid not null references assets(id),
  quantity numeric not null check(quantity > 0),
  created_at timestamptz not null default now(),
  request_fingerprint text not null
);

create table if not exists execution_ledger(
  id uuid primary key default gen_random_uuid(),
  client_order_id text not null references execution_intents(client_order_id),
  proposal_id uuid not null references trade_proposals(id),
  state text not null,
  venue_order_id text,
  status text,
  filled_quantity numeric not null default 0,
  average_price numeric,
  reason text,
  attempt integer not null default 0 check(attempt >= 0),
  request_fingerprint text not null,
  recorded_at timestamptz not null default now()
);

create table if not exists execution_reconciliations(
  id uuid primary key default gen_random_uuid(),
  client_order_id text not null references execution_intents(client_order_id),
  status text not null,
  local_ledger_id uuid not null references execution_ledger(id),
  remote_snapshot jsonb,
  reasons jsonb not null default '[]',
  reconciled_at timestamptz not null default now()
);

create index if not exists idx_execution_ledger_client_time
  on execution_ledger(client_order_id, recorded_at desc);
create index if not exists idx_execution_ledger_state
  on execution_ledger(state, recorded_at desc);
create index if not exists idx_execution_reconciliations_client_time
  on execution_reconciliations(client_order_id, reconciled_at desc);

alter table execution_intents enable row level security;
alter table execution_ledger enable row level security;
alter table execution_reconciliations enable row level security;

-- Execution records are application-owned. Policies are intentionally deferred
-- until the authenticated service integration establishes the ownership model.
