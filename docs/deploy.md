# Deploying Assay

Assay is a monorepo with two deployable parts:

- **`apps/web`** — a Next.js 15 app. **Vercel-native** (`next build` passes; ~113 kB first load).
- **`apps/api`** — a FastAPI (Python) service. **Not** Vercel-native as-is; host it
  separately and point the web app at it.

## 1. Deploy the web app to Vercel

In the Vercel dashboard → **Add New… → Project → import this repo**, then:

- **Root Directory:** `apps/web` (Vercel auto-detects Next.js; no `vercel.json` needed).
- **Build Command:** `next build` (default) · **Install:** `npm install`.
- **Environment Variable:** `NEXT_PUBLIC_API_BASE_URL = https://<your-api-host>`
  (the public URL of the deployed API from step 2). This is the only public var —
  never put server secrets in `NEXT_PUBLIC_*`.

CLI alternative:

```bash
cd apps/web
npx vercel            # first deploy / link
npx vercel --prod     # production
```

## 2. Host the API

The API holds server-only secrets (`OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`TRACERAZOR_BIN`) and runs a long-lived process, so deploy it on a Python host
(Render, Railway, Fly.io, Azure App Service, a VM, etc.):

```bash
python -m uvicorn assay_api.main:app --app-dir apps/api --host 0.0.0.0 --port $PORT
```

Set these env vars on the API host (server-only):

- `ASSAY_DB_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `ASSAY_ENV=production`
- `ASSAY_API_KEYS=<comma-separated strong shared API keys>`
- `ASSAY_REQUIRE_TENANT=1` for hosted multi-tenant mode; clients must send
  `X-Assay-Tenant` on non-health routes
- `ASSAY_CORS_ORIGINS=https://<your-web-host>` (comma-separated for multiple web origins)
- `ASSAY_RATE_LIMIT_ENABLED=1` (default) plus optional per-route limits such as `ASSAY_RATE_LIMIT_CREATE_RUN`
- `ASSAY_REQUIRE_HARDENING=1` to fail startup instead of only warning when production hardening is incomplete
- `OPENAI_API_KEY` (optional — enables the OpenAI research/extraction layer)
- `ASSAY_LLM_JUDGE_ENABLED=1` (optional) to enable semantic judge assistance
  for paraphrase rescue evidence

Production startup warns when API keys, explicit CORS origins, or rate limiting
are missing; set `ASSAY_REQUIRE_HARDENING=1` on hosted environments to make
that warning fail loud during boot. Keep `ASSAY_HTTP_CANDIDATE_ALLOW_PRIVATE`
unset or `0` in production so user-submitted HTTP candidates cannot target
loopback, RFC1918 networks, link-local addresses, or cloud metadata endpoints.
In tenant-required mode, API handlers also scope candidates, runs, events,
scorecards, lessons, and proof bundles to the active `X-Assay-Tenant`.

Secret hygiene: inject `OPENAI_API_KEY` and `SUPABASE_SERVICE_ROLE_KEY` through
the host's secret manager, never through committed files. Rotate local OpenAI
and Supabase service-role keys if the development machine has ever been shared.

> Vercel-only alternative for the API: port the FastAPI routes to Vercel Python
> Serverless Functions under `api/`. That's a follow-up — the long-running
> `uvicorn` process + the spawned TraceRazor binary fit a container host better.

## 3. Database

Supabase is already provisioned (`assay_*` tables, RLS + service-role grants).
No build step needed; just supply the env vars above. SQLite is the local fallback
when Supabase vars are absent.
