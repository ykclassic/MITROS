alter table trade_proposals
    add column if not exists owner_user_id text,
    add column if not exists risk_decision_audit_id uuid references phase4_risk_decisions(id);
create index if not exists idx_trade_proposals_owner_created
    on trade_proposals(owner_user_id, created_at desc);
create index if not exists idx_trade_proposals_risk_audit
    on trade_proposals(risk_decision_audit_id);
insert into venues (name, venue_type, active)
values ('xt.com', 'exchange', true)
on conflict (name) do update set active = true;
