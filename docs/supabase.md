# Supabase Backend

Assay can persist its core product state in Supabase Postgres while preserving SQLite as the zero-config local fallback.

## Tables

The migration creates:

- `public.assay_candidates`
- `public.assay_runs`
- `public.assay_events`
- `public.assay_scorecards`
- `public.assay_lessons`

Each table stores a typed JSON payload plus indexed columns used by the API.
Every persisted customer artifact also has a `tenant_id` column. Local mode uses
the default `local` tenant; hosted mode can require `X-Assay-Tenant` via
`ASSAY_REQUIRE_TENANT=1`.

## Security Model

- RLS is enabled on every Assay table.
- Only `service_role` receives table grants in the migration.
- Explicit `service_role` policies are present so Supabase advisors can see the intended server-only access path.
- The browser never talks directly to Supabase for these tables.
- The FastAPI server uses `SUPABASE_SERVICE_ROLE_KEY` or falls back to SQLite when Supabase is not configured.

This matches the current product shape: Assay has API-key auth and tenant
scoping enforced by the FastAPI service, but no browser-to-Supabase end-user
auth yet. When session auth is added, replace service-only writes with scoped
user/org RLS policies over the existing `tenant_id` boundary.

## Apply Locally Or Remotely

Create migration files with the Supabase CLI:

```powershell
npx supabase migration new assay_core
```

Apply to a linked Supabase project:

```powershell
npx supabase link --project-ref <project-ref>
npx supabase db push
```

Run advisors after schema changes:

```powershell
npx supabase db lint
```

If the project is inactive, restore it in Supabase first, then apply the migration.

## Runtime Env

For day-to-day local work, put server-only values in `.env.local`; `scripts/start-dev.ps1` loads `.env` and `.env.local` before starting the API and web processes.

```powershell
$env:ASSAY_DB_BACKEND="supabase"
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your-server-only-key"
```

Never expose the service role key through Next.js public env vars.

## Verify Runtime Access

From the API package path:

```powershell
$env:PYTHONPATH="apps/api"
python -m assay_api.verify_database
```

Or through the running API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/database
```

The local fallback returns `backend: sqlite`. A configured Supabase server should return `backend: supabase` and counts for all Assay tables.

## Current Connected Project

- Project ref: `yeuvdqhwqjninzifqdgz`
- API URL: `https://yeuvdqhwqjninzifqdgz.supabase.co`
- Remote migrations applied:
  - `assay_core`
  - `assay_service_role_policies`
  - `assay_diagnostic_library`
  - `assay_tenant_scope`
- Security advisors: clean after adding service-role-only policies.
- Performance advisors: only `unused_index` for `assay_events_run_sequence_idx` on the empty schema, expected until real event queries run.

The service role key is intentionally not stored in this repo.
