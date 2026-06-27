# Interviu

Interviu is a local agent interview evaluation workspace. It runs candidate agents through HR-focused adversarial interview rounds, scores reliability on held-out variants, and uses TraceRazor as the audit and proof layer for candidate-only traces.

## Local Setup

```powershell
.\scripts\setup.ps1
.\scripts\start-dev.ps1
```

The setup script installs the FastAPI dependencies, tries to install the sibling TraceRazor checkout at `C:\Users\zulfa\TraceRazor` in editable mode, and installs the Next.js workspace dependencies.

The dev launcher scans for free API and web ports, starts both servers in the background, wires `NEXT_PUBLIC_API_BASE_URL` into the web process, and writes the resolved URLs to `logs/dev-ports.json`. Stop them with:

```powershell
.\scripts\stop-dev.ps1
```

If the sibling checkout is unavailable, the API still starts and will report TraceRazor as unavailable until you install `tracerazor>=1.0.3`.

## Manual Commands

```powershell
python -m pip install -r apps/api/requirements-dev.txt
python -m pip install -e C:\Users\zulfa\TraceRazor
npm install
```

Run the API:

```powershell
python -m uvicorn interviu_api.main:app --reload --app-dir apps/api --host 127.0.0.1 --port 8000
```

Run the web app:

```powershell
npm --workspace apps/web run dev
```

If port `8000` is occupied, prefer `.\scripts\start-dev.ps1`; it will choose another API port and pass it to the web app automatically.

Run the example HTTP candidate:

```powershell
npm run dev:candidate
```

Register it in the web app with `http://127.0.0.1:8080/ask`.

Run tests:

```powershell
python -m pytest apps/api/tests
npm --workspace apps/web run test
```

## Product Surface

- The first screen is the evaluation workspace with run setup, score, proof, and a calm candidate room.
- Advanced details such as exam export, previous runs, connector probes, and trace spans stay collapsed until needed.
- HTTP candidates can be registered from the web app and use the same examiner, scoring, persistence, and TraceRazor path as mock candidates.
- `GET /runs` lists stored runs from the active database backend.
- `GET /runs/{run_id}/proof-bundle` returns a portable JSON bundle with the run, candidate, scorecard, event spans, TraceRazor summary, database health, and connector probes.
- The web app can load a previous run from the ledger and export the current proof bundle as JSON.

## MVP Boundaries

- Certificates are internal capability bars, not legal or standards compliance claims.
- Mock grading is deterministic development mode.
- Supabase is supported as the server database when server-only env vars are configured; SQLite remains the local fallback.
- MCP, OpenAI-compatible, Hugging Face, Vercel agent-browser, and local-command connectors are registry-ready, with active adapters added incrementally.

## Supabase Backend

The migration lives at `supabase/migrations/20260627031004_interviu_core.sql`.

Set these server-only env vars to use Supabase:

```powershell
$env:INTERVIU_DB_BACKEND="supabase"
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your-server-only-key"
```

Do not put the service role key in any `NEXT_PUBLIC_*` variable. See [docs/supabase.md](docs/supabase.md) for schema and RLS notes.

## Product Connectors

Interviu exposes connector readiness through `GET /connectors` and the UI connector rail. Current connector notes are in [docs/connectors.md](docs/connectors.md).

Product research notes for the AgentDojo-inspired exam shape, Hugging Face export path, and Supabase boundary are in [docs/product-research.md](docs/product-research.md).

## Pixel Sprites

The web app uses a project-local pixel sprite sheet at `apps/web/public/sprites/interviu-dojo-sprites.svg`. A generated concept sheet is saved beside it for future art direction. Details are in [docs/sprites.md](docs/sprites.md).
