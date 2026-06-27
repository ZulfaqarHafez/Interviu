-- Explicit server-only policies for Interviu tables.
-- The backend writes with a Supabase service role key. Browser clients do not
-- receive grants or policies for these tables.

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'interviu_candidates'
      and policyname = 'interviu_service_role_all_candidates'
  ) then
    create policy interviu_service_role_all_candidates
      on public.interviu_candidates
      for all
      to service_role
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'interviu_runs'
      and policyname = 'interviu_service_role_all_runs'
  ) then
    create policy interviu_service_role_all_runs
      on public.interviu_runs
      for all
      to service_role
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'interviu_events'
      and policyname = 'interviu_service_role_all_events'
  ) then
    create policy interviu_service_role_all_events
      on public.interviu_events
      for all
      to service_role
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'interviu_scorecards'
      and policyname = 'interviu_service_role_all_scorecards'
  ) then
    create policy interviu_service_role_all_scorecards
      on public.interviu_scorecards
      for all
      to service_role
      using (true)
      with check (true);
  end if;
end $$;
