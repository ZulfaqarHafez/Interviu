-- Interviu core persistence.
-- These tables are written by the FastAPI backend with a server-only
-- Supabase key. They are not exposed to browser clients.

create table if not exists public.interviu_candidates (
  id text primary key,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.interviu_runs (
  id text primary key,
  candidate_id text not null,
  exam_pack_id text not null,
  status text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.interviu_events (
  span_id text primary key,
  run_id text not null,
  sequence integer not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists interviu_events_run_sequence_idx
  on public.interviu_events (run_id, sequence);

create table if not exists public.interviu_scorecards (
  run_id text primary key,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

alter table public.interviu_candidates enable row level security;
alter table public.interviu_runs enable row level security;
alter table public.interviu_events enable row level security;
alter table public.interviu_scorecards enable row level security;

grant select, insert, update, delete on public.interviu_candidates to service_role;
grant select, insert, update, delete on public.interviu_runs to service_role;
grant select, insert, update, delete on public.interviu_events to service_role;
grant select, insert, update, delete on public.interviu_scorecards to service_role;
