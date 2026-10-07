create table if not exists profiles(
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists user_roles(
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null default 'user',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists user_entitlements(
  user_id uuid not null references auth.users(id) on delete cascade,
  entitlement text not null,
  active boolean not null default true,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  primary key(user_id, entitlement)
);

alter table research_queries add column if not exists owner_id uuid references auth.users(id) on delete set null;
alter table trade_proposals add column if not exists owner_id uuid references auth.users(id) on delete set null;
alter table approvals add column if not exists owner_id uuid references auth.users(id) on delete set null;

create index if not exists idx_research_queries_owner on research_queries(owner_id, created_at desc);
create index if not exists idx_trade_proposals_owner on trade_proposals(owner_id, created_at desc);
create index if not exists idx_approvals_owner on approvals(owner_id, decided_at desc);

alter table profiles enable row level security;
alter table user_roles enable row level security;
alter table user_entitlements enable row level security;

revoke all on table profiles, user_roles, user_entitlements from anon;
grant select, insert, update, delete on table profiles to authenticated;
grant select on table user_roles, user_entitlements to authenticated;

drop policy if exists "Users can read their own profile" on profiles;
drop policy if exists "Users can create their own profile" on profiles;
drop policy if exists "Users can update their own profile" on profiles;
drop policy if exists "Users can delete their own profile" on profiles;

create policy "Users can read their own profile"
  on profiles for select to authenticated
  using ((select auth.uid()) = id);

create policy "Users can create their own profile"
  on profiles for insert to authenticated
  with check ((select auth.uid()) = id);

create policy "Users can update their own profile"
  on profiles for update to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

create policy "Users can delete their own profile"
  on profiles for delete to authenticated
  using ((select auth.uid()) = id);

drop policy if exists "Users can read their own role" on user_roles;
create policy "Users can read their own role"
  on user_roles for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users can read their own entitlements" on user_entitlements;
create policy "Users can read their own entitlements"
  on user_entitlements for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can read their own research queries"
  on research_queries for select to authenticated
  using ((select auth.uid()) = owner_id);

create policy "Users can read their own trade proposals"
  on trade_proposals for select to authenticated
  using ((select auth.uid()) = owner_id);

create policy "Users can read their own approvals"
  on approvals for select to authenticated
  using ((select auth.uid()) = owner_id);

revoke all on table research_queries, trade_proposals, approvals from anon;
grant select on table research_queries, trade_proposals, approvals to authenticated;
