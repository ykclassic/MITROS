create extension if not exists pgcrypto;

create table if not exists assets(id uuid primary key default gen_random_uuid(),symbol text not null,asset_class text not null,canonical_symbol text not null,active boolean not null default true,created_at timestamptz not null default now(),unique(asset_class,canonical_symbol));
create table if not exists venues(id uuid primary key default gen_random_uuid(),name text not null unique,venue_type text not null,active boolean not null default true,created_at timestamptz not null default now());

create table if not exists market_data(id uuid primary key default gen_random_uuid(),asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),timeframe text not null,observed_at timestamptz not null,received_at timestamptz not null,values jsonb not null,provenance jsonb not null);
create table if not exists candles(id uuid primary key default gen_random_uuid(),asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),timeframe text not null,open_time timestamptz not null,close_time timestamptz not null,open numeric not null,high numeric not null,low numeric not null,close numeric not null,volume numeric,provenance jsonb not null,unique(asset_id,venue_id,timeframe,open_time));

create table if not exists features(id uuid primary key default gen_random_uuid(),asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),timeframe text not null,as_of timestamptz not null,feature_set_version text not null,values jsonb not null,provenance jsonb not null);
create table if not exists regimes(id uuid primary key default gen_random_uuid(),asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),as_of timestamptz not null,regime text not null,confidence numeric not null check(confidence between 0 and 1),version text not null,provenance jsonb not null);

create table if not exists strategies(id uuid primary key default gen_random_uuid(),strategy_key text not null unique,name text not null,version text not null,active boolean not null default true,created_at timestamptz not null default now());
create table if not exists strategy_signals(id uuid primary key default gen_random_uuid(),strategy_id uuid not null references strategies(id),asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),direction text,confidence numeric not null check(confidence between 0 and 1),payload jsonb not null,observed_at timestamptz not null,provenance jsonb not null,created_at timestamptz not null default now());
create table if not exists strategy_performance(id uuid primary key default gen_random_uuid(),strategy_id uuid not null references strategies(id),regime text,timeframe text,as_of timestamptz not null,metrics jsonb not null,version text not null);

create table if not exists models(id uuid primary key default gen_random_uuid(),model_key text not null unique,name text not null,active boolean not null default true);
create table if not exists model_versions(id uuid primary key default gen_random_uuid(),model_id uuid not null references models(id),version text not null,artifact_uri text,checksum text,created_at timestamptz not null default now(),unique(model_id,version));
create table if not exists model_predictions(id uuid primary key default gen_random_uuid(),model_version_id uuid not null references model_versions(id),asset_id uuid not null references assets(id),as_of timestamptz not null,prediction jsonb not null,provenance jsonb not null);
create table if not exists model_validation(id uuid primary key default gen_random_uuid(),model_version_id uuid not null references model_versions(id),method text not null,metrics jsonb not null,validated_at timestamptz not null);
create table if not exists model_drift(id uuid primary key default gen_random_uuid(),model_version_id uuid not null references model_versions(id),metric text not null,value numeric not null,threshold numeric not null,detected_at timestamptz not null);

create table if not exists trade_proposals(id uuid primary key,asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),direction text not null,entry numeric not null,stop numeric not null,target numeric not null,risk_reward numeric not null check(risk_reward>0),position_size numeric not null check(position_size>0),risk_decision text not null,risk_reasons jsonb not null default '[]',approval_status text not null default 'PENDING',approval_actor text,approval_at timestamptz,execution_status text not null default 'NOT_AUTHORIZED',expires_at timestamptz not null,payload jsonb not null,provenance jsonb not null,created_at timestamptz not null default now());
create table if not exists risk_decisions(id uuid primary key default gen_random_uuid(),trade_proposal_id uuid not null references trade_proposals(id),decision text not null,reasons jsonb not null,engine_version text not null,evaluated_at timestamptz not null);
create table if not exists approvals(id uuid primary key default gen_random_uuid(),trade_proposal_id uuid not null references trade_proposals(id),actor text not null,decision text not null,idempotency_key text not null unique,decided_at timestamptz not null default now(),metadata jsonb not null default '{}');

create table if not exists orders(id uuid primary key default gen_random_uuid(),trade_proposal_id uuid not null references trade_proposals(id),client_order_id text not null unique,venue_order_id text,status text not null,submitted_at timestamptz,updated_at timestamptz not null default now(),payload jsonb not null default '{}');
create table if not exists executions(id uuid primary key default gen_random_uuid(),order_id uuid not null references orders(id),venue_execution_id text,status text not null,filled_quantity numeric not null default 0,average_price numeric,occurred_at timestamptz not null,payload jsonb not null default '{}');
create table if not exists fills(id uuid primary key default gen_random_uuid(),execution_id uuid not null references executions(id),quantity numeric not null,price numeric not null,fee numeric,occurred_at timestamptz not null,payload jsonb not null default '{}');
create table if not exists positions(id uuid primary key default gen_random_uuid(),asset_id uuid not null references assets(id),venue_id uuid not null references venues(id),quantity numeric not null,average_price numeric,status text not null,updated_at timestamptz not null default now(),unique(asset_id,venue_id));

create table if not exists portfolio_snapshots(id uuid primary key default gen_random_uuid(),as_of timestamptz not null,balances jsonb not null,exposure jsonb not null,provenance jsonb not null);
create table if not exists risk_snapshots(id uuid primary key default gen_random_uuid(),as_of timestamptz not null,exposure jsonb not null,drawdown numeric,margin numeric,limits jsonb not null,provenance jsonb not null);
create table if not exists trade_outcomes(id uuid primary key default gen_random_uuid(),trade_proposal_id uuid not null references trade_proposals(id),outcome text not null,pnl numeric,return_r numeric,closed_at timestamptz,payload jsonb not null);
create table if not exists signal_outcomes(id uuid primary key default gen_random_uuid(),strategy_signal_id uuid not null references strategy_signals(id),outcome text not null,return_r numeric,evaluated_at timestamptz not null,payload jsonb not null);
create table if not exists strategy_attribution(id uuid primary key default gen_random_uuid(),trade_outcome_id uuid not null references trade_outcomes(id),strategy_id uuid not null references strategies(id),contribution numeric,reason text);

create table if not exists research_queries(id uuid primary key default gen_random_uuid(),actor text,query text not null,created_at timestamptz not null default now());
create table if not exists research_answers(id uuid primary key default gen_random_uuid(),query_id uuid not null references research_queries(id),answer text not null,model_version text,created_at timestamptz not null default now());
create table if not exists research_evidence(id uuid primary key default gen_random_uuid(),answer_id uuid not null references research_answers(id),evidence_type text not null,reference text not null,snapshot jsonb not null);

create table if not exists system_events(id uuid primary key default gen_random_uuid(),event_type text not null,aggregate_id uuid not null,occurred_at timestamptz not null,recorded_at timestamptz not null default now(),producer text not null,producer_version text not null,correlation_id uuid not null,causation_id uuid,schema_version integer not null default 1,payload jsonb not null,provenance jsonb not null default '[]');
create table if not exists audit_events(id uuid primary key default gen_random_uuid(),actor text,action text not null,aggregate_type text not null,aggregate_id uuid,occurred_at timestamptz not null default now(),metadata jsonb not null default '{}');

create index if not exists idx_events_aggregate on system_events(aggregate_id,occurred_at);
create index if not exists idx_events_type on system_events(event_type,occurred_at);
create index if not exists idx_proposals_status on trade_proposals(approval_status,execution_status);
create index if not exists idx_candles_lookup on candles(asset_id,venue_id,timeframe,open_time desc);
create index if not exists idx_research_queries_created on research_queries(created_at desc);

-- Baseline RLS is enabled now; policies are added with authenticated application ownership in the Auth integration phase.
do $$
declare t text;
begin
  foreach t in array array['assets','venues','market_data','candles','features','regimes','strategies','strategy_signals','strategy_performance','models','model_versions','model_predictions','model_validation','model_drift','trade_proposals','risk_decisions','approvals','orders','executions','fills','positions','portfolio_snapshots','risk_snapshots','trade_outcomes','signal_outcomes','strategy_attribution','research_queries','research_answers','research_evidence','system_events','audit_events']
  loop
    execute format('alter table %I enable row level security',t);
  end loop;
end $$;
