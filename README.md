![Assay — bring your agent.md, find out where it breaks](apps/web/public/brand/assay-og.png)

# Assay

**Assay is a pre-deployment litmus test for AI agents.** Bring the `agent.md` /
`AGENTS.md` definition you already have, and Assay runs it through an adversarial
exam, grades it on the failure modes that get agents pulled from production, and
hands you a ranked list of what to fix before you ship — no SDK and no test
harness to write.

> Bring your agent.md. Find out where it breaks.

## What it does

- **Selection, not creation.** Paste or drop an `agent.md`, or start from a
  built-in template. Assay treats that definition as the candidate under test.
- **Adversarial exam.** Each run fires 20+ probes across six failure categories —
  compliance, prompt injection, fairness, confidentiality, refusal boundaries,
  and ambiguity handling — including held-out prompts the agent has never seen.
- **Held-out certification.** Verdicts are gated at `pass^k`: an agent has to
  hold the line across repeated held-out re-runs, so a single lucky pass never
  certifies it as ready to ship.
- **A verdict you can act on.** You get a FAIL → RISKY → SHIP band, a per-capability
  score breakdown, and a severity-ranked "what to fix" list tied back to the
  failing trace.
- **An audited paper trail.** Every run is persisted as an experiment with a
  portable proof bundle (run, candidate, scorecard, event spans, TraceRazor audit
  summary, and a refined agent spec) you can export as JSON.
- **Runs offline by default.** Mock grading is deterministic and needs no keys;
  an optional OpenAI layer evaluates your real agent live, and gracefully
  degrades to a demo verdict (with a banner) if a key is missing or rate-limited.

## Screenshots

### Drop in an `agent.md`

The front door: paste or upload an agent definition, pick a template, and run the
litmus test.

![Assay intake screen](docs/images/01-landing.png)

### Watch it survive an adversarial exam

Probes stream live as the agent is stress-tested across each failure category.

![Assay run streaming](docs/images/02-judging.png)

### Get a verdict and a ranked list of fixes

A ship/fail verdict, per-capability scores, and a severity-ordered list of what to
fix before you deploy. (Here a high raw score still fails the gate because
compliance broke on held-out variants.)

![Assay verdict and fixes](docs/images/03-verdict.png)

### Every run is a tracked experiment

The workspace keeps a ledger of runs — scored, certified at `pass^k`, and open to
compare against a previous run or inspect the trace.

![Assay experiments ledger](docs/images/05-experiments.png)

## Quick Start

```powershell
.\scripts\setup.ps1
.\scripts\start-dev.ps1
```

`setup.ps1` installs the FastAPI dependencies, tries to install the sibling
TraceRazor checkout at `C:\Users\zulfa\TraceRazor` in editable mode, and installs
the Next.js workspace dependencies.

`start-dev.ps1` scans for free API and web ports, starts both servers in the
background, wires `NEXT_PUBLIC_API_BASE_URL` into the web process, and writes the
resolved URLs to `logs/dev-ports.json`. Open the web URL it prints, paste an
`agent.md`, and run. Stop both servers with:

```powershell
.\scripts\stop-dev.ps1
```

If the sibling TraceRazor checkout is unavailable, the API still starts and
reports TraceRazor as unavailable until you install `tracerazor>=1.0.3`.

## Manual Commands

```powershell
python -m pip install -r apps/api/requirements-dev.txt
python -m pip install -e C:\Users\zulfa\TraceRazor
npm install
```

Run the API:

```powershell
python -m uvicorn assay_api.main:app --reload --app-dir apps/api --host 127.0.0.1 --port 8000
```

Run the web app:

```powershell
npm --workspace apps/web run dev
```

If port `8000` is occupied, prefer `.\scripts\start-dev.ps1`; it will choose
another API port and pass it to the web app automatically.

Run the example HTTP candidate (then register it in the web app at
`http://127.0.0.1:8080/ask`):

```powershell
npm run dev:candidate
```

Run tests:

```powershell
python -m pytest apps/api/tests
npm --workspace apps/web run test
```

## Run Assay in CI

Assay ships a CLI so you can gate deploys on a held-out verdict from a shell or a
pipeline:

```powershell
$env:PYTHONPATH="apps/api"
python -m assay_api.cli run --agent-md .\agent.md --pack hr-v1 --pass-threshold 0.8
```

Useful flags: `--k` (trials per seen/held-out item), `--live` (evaluate the agent
with OpenAI instead of mock mode), and `--json-out` / `--proof-out` /
`--summary-out` to write the scorecard JSON, proof bundle JSON, and Markdown
verdict summary. The reusable GitHub Action lives at `.github/actions/assay` and
uploads those three artifacts.

## How a run flows

`/` paste or upload `agent.md` → register candidate → stream the adversarial
judging → verdict, with a ranked "what to fix" list → open the workspace at
`/runs/[id]` for the verdict band, capability radar, run comparison, learning
trend, diagnostics, reviewers, and the trace drawer.

## Product Surface

- The first screen is the agent intake front door; the routed workspace exposes
  **Experiments** (`/runs`), **Suites** (`/suites`), and **Agents** (`/agents`),
  with a `⌘K` command palette for jumping between them.
- A free-text job scope can be turned into decision logic: role analysis
  deterministically maps job-scope phrases to competencies, expected checks, and
  recommended sub-agents with a traceable evidence chain, picks the exam pack, and
  flags protected-attribute language as compliance notes only (never
  requirements). Available via `POST /role-analysis`,
  `GET /runs/{run_id}/role-analysis`, and embedded in the proof bundle; details
  are in [docs/role-intelligence.md](docs/role-intelligence.md).
- HTTP candidates use the same examiner, scoring, persistence, and TraceRazor
  path as mock candidates.
- The Agent Refinery turns each run into a refined `AGENTS.md` for the candidate
  plus grounded sub-agent recommendations; details are in
  [docs/agent-refinery.md](docs/agent-refinery.md).
- An optional OpenAI layer can research "what this agent should be" on demand —
  fast (grounded in the run) or deep (web search with cited sources) — via
  `POST /runs/{run_id}/agent-spec/research?mode=fast|deep`. The key is read
  server-side only from `OPENAI_API_KEY`/`openai_key` in a git-ignored root
  `.env`/`env`; with no key the feature reports `unavailable` and the rest of
  Assay keeps working offline.
- `GET /runs` lists stored runs from the active database backend;
  `GET /runs/{run_id}/agent-spec` returns the refined `assay.agent_spec.v1`
  definition; `POST /runs/{run_id}/agent-spec/export-files` writes `AGENTS.md` plus
  one `.md` per recommended sub-agent; `GET /runs/{run_id}/proof-bundle` returns
  the portable proof bundle.
- Suite import/export, role analysis, HTTP candidates, research, and server-only
  connector surfaces are tracked in
  [docs/backend-surfaces.md](docs/backend-surfaces.md).

## MVP Boundaries

- Certificates are internal capability bars, not legal or standards compliance
  claims.
- Mock grading is deterministic development mode.
- Optional semantic judge assistance is disabled by default; set
  `ASSAY_LLM_JUDGE_ENABLED=1` server-side to allow bounded LLM paraphrase
  rescue evidence in scorecards.
- Supabase is supported as the server database when server-only env vars are
  configured; SQLite remains the local fallback.
- MCP, OpenAI-compatible, Hugging Face, Vercel agent-browser, and local-command
  connectors are registry-ready, with active adapters added incrementally.

## Supabase Backend

The migration lives at `supabase/migrations/20260627031004_interviu_core.sql`.

Set these server-only env vars to use Supabase:

```powershell
$env:ASSAY_DB_BACKEND="supabase"
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your-server-only-key"
```

Do not put the service role key in any `NEXT_PUBLIC_*` variable. See
[docs/supabase.md](docs/supabase.md) for schema and RLS notes.

## Connectors & Research

Assay exposes connector readiness through `GET /connectors` and the UI connector
rail. Current connector notes are in [docs/connectors.md](docs/connectors.md), and
product research notes for the AgentDojo-inspired exam shape, Hugging Face export
path, and Supabase boundary are in
[docs/product-research.md](docs/product-research.md).

---

> **Note:** the package, API module, and many env vars still use the original
> `assay` name internally; **Assay** is the product name. Renaming the code
> namespace is intentionally deferred to avoid churn.
