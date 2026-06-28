# Agent Refinery

The Agent Refinery turns one interview run into a refined, reusable agent
definition plus grounded sub-agent recommendations. It closes the loop on an
Assay run: the examiner, grader panel, lesson library, and the TraceRazor
trace auditor produce a scorecard, and the refinery converts that scorecard into
an `AGENTS.md` the candidate agent can actually ship with.

The refinery is **deterministic** — it never calls an LLM. Every line in the
output is traceable to a concrete signal in the run, which keeps the artifact
offline, fast, and unit-testable. An optional LLM polishing pass could later
wrap `build_agent_spec` without changing its contract.

## Inputs

`apps/api/assay_api/agent_refinery.py::build_agent_spec` reads:

- the run config (`k`, `competency_threshold`, `max_transfer_gap`),
- the scorecard (`held_out_scores`, `transfer_gap`, `pass_at_k`, `trace_audit`,
  `failure_reasons`),
- the exam pack (per-competency rubrics and expected checks), and
- the run event spans (retained lessons recorded by the lesson library).

## Output: `assay.agent_spec.v1`

```jsonc
{
  "schema": "assay.agent_spec.v1",
  "run_id": "run_...",
  "candidate_id": "cand_...",
  "candidate_name": "Demo Candidate",
  "readiness": "ready | refine | needs_subagents",
  "headline": "one-line verdict",
  "agent_markdown": "# ... refined AGENTS.md ...",
  "strengths": ["Compliance (held-out 96%)"],
  "gaps": ["Fairness: held-out 50% < 80% threshold"],
  "tracerazor_actions": ["TraceRazor TAS 88/100 [Good] — passed."],
  "sub_agents": [ /* SubAgentSpec[] */ ],
  "metrics": { "tas_score": 88, "recommended_subagents": 0, "...": "..." }
}
```

### Readiness

- `ready` — the run is certified (passed `pass^k` on held-out variants, within
  transfer-gap and TAS thresholds). Sub-agents may still be suggested as
  *optional* scaling delegates.
- `needs_subagents` — at least one competency failed and is best handed to a
  focused specialist sub-agent.
- `refine` — not certified, but the gaps are addressed by must-fix rules rather
  than a sub-agent split.

### The refined `AGENTS.md`

`agent_markdown` is a complete operating spec with: role, readiness, verified
operating principles (passing competencies + their rubric), must-fix rules
(failing competencies), retained lessons, a TraceRazor trace-discipline section,
a delegation list, and standing guardrails.

## Sub-agent recommendations

Each `SubAgentSpec` carries its own `definition_markdown` (a ready-to-save
sub-agent `.md`), a `sprite` for the UI, a `priority`, a `trigger` (the signal
that recruited it), and a `delegation_rule`. Recommendations are derived from:

| Signal in the run | Recommended sub-agent | Priority |
| --- | --- | --- |
| A competency fails `pass^k` | Competency specialist (e.g. Fairness Counterfactual Checker) | recommended |
| `transfer_gap` exceeds the run threshold | Held-Out Verifier | recommended |
| TraceRazor TAS below threshold / unavailable / errored | Trace Auditor | recommended |
| TraceRazor passed but proposed fixes | Trace Auditor | recommended |
| Certified run, high volume expected | Trace Auditor + weakest-competency specialist | optional |

Specialist templates live in `_SUBAGENT_TEMPLATES` and cover the HR and
adversarial competencies (`prompt_injection_resilience`, `tool_output_hygiene`,
`data_minimization`, `compliance`, `fairness`, `ambiguity_handling`,
`refusal_boundaries`, `interview_ethics`), with a generic fallback for custom
exam packs.

The **Trace Auditor** sub-agent is the direct TraceRazor handoff: its definition
instructs the lead agent to wrap each run in `tracerazor.Tracer`, submit the
candidate-only trace through `TraceRazorClient.analyse`, read `report.fixes`, and
apply the patches whose savings justify the change before shipping.

## API

- `GET /runs/{run_id}/agent-spec` — returns the `assay.agent_spec.v1`
  payload. `404` if the run is unknown, `409` if it has no scorecard yet.
- `POST /runs/{run_id}/agent-spec/export-files` — writes `AGENTS.md`,
  `agent-spec.json`, and one `subagents/<id>.md` per recommendation under
  `exports/agents/<run_id>/`, returning the written paths.
- `GET /runs/{run_id}/proof-bundle` — embeds the agent spec under `agent_spec`
  so the portable proof bundle is self-contained.

## Web surface

The evaluation workspace renders the full agent panel (examiner, judge panel,
lesson library, TraceRazor auditor, simulator) as sprite characters that
activate during a run, and an **Agent refinery** section that shows the
readiness verdict, strengths/gaps counts, and the recommended sub-agents. The
trace drawer renders the refined `AGENTS.md`, each sub-agent card, and per-file
download links.

## OpenAI research (optional enrichment)

The deterministic spec is always produced offline. On top of it, an optional
OpenAI layer answers "what should this agent be?" on demand:

- **Fast** (`mode=fast`, default) — one structured reasoning call (default
  `gpt-4.1`, override with `ASSAY_OPENAI_MODEL`) grounded only in the run's
  own evaluation evidence. Quick and cheap, no web access, no citations.
- **Deep** (`mode=deep`) — OpenAI deep research (default
  `o4-mini-deep-research`, override with `ASSAY_OPENAI_DEEP_MODEL`) using the
  web-search tool, so recommendations are grounded in current external best
  practices and return cited sources. Slower (can take minutes) and costs more.

### Endpoint

`POST /runs/{run_id}/agent-spec/research?mode=fast|deep` returns an
`AgentResearch` payload: `summary`, `brief_markdown`, `recommended_tools`,
`recommended_subagents` (`{name, purpose}`), `risks`, and `sources` (deep mode).
When no key is configured it returns `status="unavailable"` (with a hint) rather
than failing, so the rest of Assay keeps working offline. SDK/network/parse
failures return `status="error"` and degrade gracefully.

### Configuration

The OpenAI key is read **server-side only** and is never exposed to the browser.
`agent_research.load_local_env` populates the process environment (without
overriding existing vars) from, in order, `ASSAY_ENV_FILE`, then `.env`, then
`env` at the project root, and the key is resolved from `OPENAI_API_KEY`,
`OPENAI_KEY`, or `openai_key`:

```
# project-root .env (git-ignored)
OPENAI_API_KEY=sk-...
# optional overrides
ASSAY_OPENAI_MODEL=gpt-4.1
ASSAY_OPENAI_DEEP_MODEL=o4-mini-deep-research
ASSAY_OPENAI_TIMEOUT_S=300
```

Running research sends the run's candidate answers, scores, and the refined
spec to OpenAI, so it is always an explicit, on-demand action triggered from the
**Agent refinery** panel ("OpenAI research" / "Deep research (web)").

## Boundaries

Refined specs are internal capability artifacts derived from deterministic mock
grading — not legal or standards compliance claims, mirroring the rest of the
Assay MVP.
