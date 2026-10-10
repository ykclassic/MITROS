create table if not exists phase4_risk_decisions (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    proposal_id text not null,
    idempotency_key text not null,
    disposition text not null check (disposition in ('APPROVED', 'REJECTED')),
    engine_version text not null,
    request_snapshot jsonb not null,
    policy_snapshot jsonb not null,
    decision_snapshot jsonb not null,
    created_at timestamptz not null default now(),
    unique (user_id, idempotency_key)
);

create index if not exists idx_phase4_risk_decisions_user_created
    on phase4_risk_decisions(user_id, created_at desc);
create index if not exists idx_phase4_risk_decisions_proposal
    on phase4_risk_decisions(proposal_id, created_at desc);

alter table phase4_risk_decisions enable row level security;
revoke all on table phase4_risk_decisions from anon, authenticated;
grant all on table phase4_risk_decisions to service_role;
