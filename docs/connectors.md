# Assay Connectors

Assay has a small connector registry exposed by `GET /connectors`. The registry is product-facing: it tells the operator what can run today, what is configured, and what is queued next.

`GET /connectors/probe` adds read-only evidence for the same surface. It uses allowlisted checks only: TraceRazor import status, active database health, `hf version` plus auth state, and `agent-browser --help` when that command is available. The web app renders these probes under each connector so an operator can see the proof behind a ready, planned, connected, or warning state.

## Ready Now

- `mock`: deterministic local HR candidate for demos and tests.
- `http`: black-box candidate endpoint using the same examiner and grading path as the mock agent.
- `supabase`: active when `ASSAY_DB_BACKEND=supabase`, `SUPABASE_URL`, and a server-only Supabase key are present. SQLite remains the local default even if Supabase secrets are present.
- `hugging-face`: marked ready when the `hf` CLI is on PATH. In this workspace `hf version` reports `huggingface_hub 0.36.2`, the account probe reports not logged in, and this installed CLI exposes download/upload/jobs rather than the newer dataset/model search commands.
  - `POST /exam-packs/{pack_id}/export-files` writes a Hub-ready folder under `exports/exam-packs/{pack_id}` with `README.md`, `data/assay_exam_rows.jsonl`, and `assay-exam-pack.json`.

## Planned

- `vercel-agent-browser`: browser automation for deployed or local workspace verification. The `agent-browser` CLI was not on PATH in this workspace, so the app keeps Playwright as the verified local path.
- `openai-compatible`: direct model plus system-prompt candidate adapter.
- `local-command`: wraps a local executable candidate behind the `ask(context, question)` contract.
- `mcp-server`: wraps an MCP-hosted agent or tool server as a candidate adapter.

## Adapter Contract

Every active candidate connector must produce:

```json
{
  "answer": "string",
  "reasoning": "string",
  "tool_calls": [],
  "latency_ms": 120,
  "tokens": { "input": 10, "output": 20, "total": 30 }
}
```

Assay stores the full span timeline, then sends a bounded candidate-only reasoning/tool slice to TraceRazor. Tune the slice and runtime limit with `ASSAY_TRACERAZOR_MAX_STEPS` and `ASSAY_TRACERAZOR_TIMEOUT_S`.

## Local HTTP Starter

The repo includes a runnable HTTP candidate at `examples/http_candidate/server.py`. Start it with:

```powershell
npm run dev:candidate
```

Then register `http://127.0.0.1:8080/ask` in the app. The starter is intentionally simple: it proves the black-box candidate contract, exercises the same grading path as real HTTP agents, and gives TraceRazor candidate-only reasoning and tool-call material to audit.

## Proof Bundles

`GET /runs/{run_id}/proof-bundle` packages a persisted run into `assay.proof_bundle.v1`:

- run config and candidate config
- scorecard and TraceRazor audit summary
- ordered event spans
- active database health
- connector registry and probe evidence

The web app uses this endpoint for the run ledger and export action. This keeps SQLite and Supabase behavior identical at the product layer.

## Activation Checklist

The web app keeps non-passing connector probes in collapsed system details. This is intentionally read-only: it never asks for secrets in the browser and only reports server-side status such as missing Supabase service-role env vars, missing Hugging Face auth, or `agent-browser` not being on PATH.
