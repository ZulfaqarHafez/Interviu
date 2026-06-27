-- Interviu diagnostic library.
-- Persistent, per-candidate lessons that survive across runs so later runs can
-- re-apply what earlier runs learned (the closed learning loop). Written by the
-- FastAPI backend with a server-only Supabase key; never exposed to browsers.

create table if not exists public.interviu_lessons (
  id text primary key,
  candidate_id text not null,
  exam_pack_id text not null,
  competency text not null,
  active boolean not null default true,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists interviu_lessons_candidate_idx
  on public.interviu_lessons (candidate_id, exam_pack_id, competency, active);

alter table public.interviu_lessons enable row level security;

grant select, insert, update, delete on public.interviu_lessons to service_role;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'interviu_lessons'
      and policyname = 'interviu_service_role_all_lessons'
  ) then
    create policy interviu_service_role_all_lessons
      on public.interviu_lessons
      for all
      to service_role
      using (true)
      with check (true);
  end if;
end $$;
