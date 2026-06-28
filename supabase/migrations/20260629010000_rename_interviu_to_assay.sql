-- Product rename interviu -> assay: rename the persisted schema objects so a
-- Supabase project provisioned by the earlier migrations matches the renamed
-- application code (which now reads/writes assay_* tables). Idempotent: each
-- statement is a no-op if the legacy object is already gone.

alter table if exists public.interviu_candidates rename to assay_candidates;
alter table if exists public.interviu_runs rename to assay_runs;
alter table if exists public.interviu_events rename to assay_events;
alter table if exists public.interviu_scorecards rename to assay_scorecards;
alter table if exists public.interviu_lessons rename to assay_lessons;

alter index if exists public.interviu_candidates_tenant_created_idx rename to assay_candidates_tenant_created_idx;
alter index if exists public.interviu_events_run_sequence_idx rename to assay_events_run_sequence_idx;
alter index if exists public.interviu_events_tenant_run_sequence_idx rename to assay_events_tenant_run_sequence_idx;
alter index if exists public.interviu_lessons_candidate_idx rename to assay_lessons_candidate_idx;
alter index if exists public.interviu_lessons_tenant_candidate_idx rename to assay_lessons_tenant_candidate_idx;
alter index if exists public.interviu_runs_tenant_created_idx rename to assay_runs_tenant_created_idx;

-- Rename any surviving interviu_* RLS policies to assay_* on their (now renamed) tables.
do $$
declare
  r record;
begin
  for r in
    select policyname, tablename
    from pg_policies
    where schemaname = 'public' and policyname like 'interviu\_%'
  loop
    execute format(
      'alter policy %I on public.%I rename to %I',
      r.policyname, r.tablename, replace(r.policyname, 'interviu_', 'assay_')
    );
  end loop;
end $$;
