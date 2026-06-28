# Role Intelligence

Role intelligence turns a free-text **job scope** into the competencies, expected
checks, and sub-agents the candidate agent should be evaluated against — and it
shows its work. Where the [Agent Refinery](agent-refinery.md) closes the loop
*after* a run, role intelligence opens it *before* one: given "here is the role,
here is what it does," it decides what the interview should test and exposes a
traceable reason for every decision.

The mapper is **deterministic-first** and **offline-safe**. A keyword pass with
no network and no LLM produces the full analysis; an optional OpenAI extraction
pass only improves recall. Every requirement is backed by an evidence chain, so
the decision is always explainable.

`apps/api/assay_api/role_intelligence.py` is the implementation.

## JobScope

A `JobScope` (`apps/api/assay_api/models.py`) is the structured view of a
role description. `raw_text` is the candidate-supplied free text; the structured
fields are populated either by the deterministic keyword extractor or by the
optional OpenAI extraction pass, and `extraction` records which produced them.

```jsonc
{
  "raw_text": "Senior HR coordinator who screens and ranks candidates...",
  "title": "HR Coordinator",
  "seniority": "intern | junior | mid | senior | lead | executive | unspecified",
  "responsibilities": ["..."],
  "required_skills": ["..."],
  "nice_to_have": ["..."],
  "qualifications": ["..."],
  "domain": "...",
  "risks": ["..."],
  "compliance_flags": ["protected:age", "..."],
  "extraction": "none | keyword | openai-fast | openai-deep"
}
```

`raw_text` is capped at 8000 characters before it reaches the keyword scanner or
an LLM call.

## Decision logic (deterministic mapper)

`analyze_job_scope(job_scope, override_pack_id=None)` maps the scope to a
`RoleAnalysis`. It runs entirely offline and reuses the registered exam packs and
the Agent Refinery's sub-agent templates, so recommendations stay traceable and
never duplicate template logic.

The pipeline:

1. **Build a haystack.** `raw_text`, `title`, `domain`, and every structured
   list (`responsibilities`, `required_skills`, `nice_to_have`, `qualifications`,
   `risks`) are lowercased and joined. Seniority is detected from the text when
   the scope leaves it `unspecified`.
2. **Floor competencies first.** `compliance` and `fairness` (both from `hr-v1`)
   are always evaluated, even when no keyword hits, recorded with the
   `r-floor` rule so they always carry a deterministic source.
3. **Keyword rules.** Each rule in `_COMPETENCY_RULES` maps signal phrases to one
   competency tested by a specific pack. A matched phrase adds a
   `RequirementSource` to that competency.
4. **Resolve expected checks.** For each matched competency, the mapper looks up
   the concrete `expected_check_ids` from the named pack (falling back to any
   registered pack that tests it), and records which pack covers it.
5. **Rationale + uncovered tracking.** Each requirement gets a one-line rationale
   built from its strongest signal phrase (or a baseline note for floor
   competencies). Competencies no registered pack tests are listed in
   `uncovered_competencies`.
6. **Pick the recommended pack.** The pack contributing the most matched
   competencies wins; ties break toward the default `hr-v1`, then registration
   order. An `override_pack_id` forces a specific pack. Other contributing packs
   become `supplemental_pack_ids`.
7. **Recommend sub-agents.** One specialist per matched competency, built via the
   refinery's `_specialist` template (so the sprite, delegation rule, and
   definition markdown match the refinery's output), then capped via
   `_cap_sub_agents`. Requirement → sub-agent links are corrected after capping
   so they never point at a dropped sub-agent.
8. **Protected pass (EEOC safeguard).** See below.

### Decision logic visibility

The visibility is in the `RequirementSource` chain. Each
`CompetencyRequirement` carries:

- `competency` / `label` — the competency and its display label,
- `rationale` — why it was selected, in one line,
- `sources` — a list of `RequirementSource` evidence entries, each with the
  `phrase` (the sentence-window of text that matched), the `field` it came from
  (`raw_text` or `floor`), the `rule_id` that fired, and a `weight`,
- `expected_check_ids` — the concrete checks the competency is tested by,
- `recommended_subagent_id` — the specialist proposed for it (or `null` if
  capped out),
- `priority` and `covered_by_pack`.

So a reader can trace: *this phrase in the job scope* → *fired this rule* →
*selected this competency* → *tested by these checks in this pack* → *handed to
this sub-agent*. Nothing is opaque.

### Floor competencies

`compliance` and `fairness` are floor competencies (`_FLOOR_COMPETENCIES`). They
are always evaluated regardless of the scope text, so every HR analysis is held
to a baseline screening bar. They appear with a `r-floor` source
("floor competency (always evaluated)") and a baseline rationale when no keyword
signal also recruited them.

### Pack auto-selection

The mapper counts how many competencies each pack contributes (`pack_votes`) and
picks the highest. The current packs are `hr-v1` (compliance, fairness,
ambiguity handling, refusal boundaries, interview ethics) and `hr-injection-v1`
(prompt-injection resilience, tool-output hygiene, data minimization). A scope
heavy on resumes/attachments/PII therefore steers toward `hr-injection-v1`,
while a plain screening scope stays on `hr-v1`. `override_pack_id` overrides the
vote entirely.

## EEOC-safe protected-attribute handling

A hard EEOC safeguard runs on **every** analysis. Protected-attribute signals —
age, national origin, family/parental status, disability, religion
(`_PROTECTED_SIGNALS`) — are recorded as **compliance flags and notes only and
are NEVER turned into a competency requirement**.

When the scope text matches a protected signal, the analysis:

- adds a `protected:<category>` entry to `compliance_flags` (de-duplicated), and
- appends a `compliance_notes` line naming the category and the matched phrases,
  stating the language "is recorded as a compliance flag only and is never used
  as a screening requirement."

The optional OpenAI extraction path enforces the same contract from the other
side: its system prompt extracts job-related requirements only and flags any
protected-attribute language separately as `protected:<category>`, with an
explicit instruction never to list a protected trait or preference as a
responsibility, skill, or qualification.

## Optional OpenAI extraction (recall improver)

`extract_job_scope_openai(raw_text, mode="fast")` parses the free text into a
structured `JobScope` using OpenAI. It is purely a recall improver: the
deterministic mapper still runs afterward, so the decision stays explainable.

It reuses the Agent Refinery's key/fallback pattern: the key is resolved
server-side via `agent_research.resolve_openai_key` (`OPENAI_API_KEY` /
`OPENAI_KEY` / `openai_key` from a git-ignored root `.env`/`env`). When **no key
is configured the function returns `None`**, so the caller falls back to a
keyword-only `JobScope` and the feature degrades gracefully. Extraction uses the
default fast model with a strict JSON-schema response (`_JOB_SCOPE_JSON_SCHEMA`),
timeout configurable via `ASSAY_OPENAI_TIMEOUT_S`. `mode` is `fast` or
`deep`; the resulting `extraction` field is `openai-fast` or `openai-deep`.

## Payload: `assay.role_analysis.v1`

`role_analysis_payload(job_scope, override_pack_id=None)` returns the
schema-tagged JSON (`{"schema": "assay.role_analysis.v1", ...}`), the
serialized `RoleAnalysis`:

```jsonc
{
  "schema": "assay.role_analysis.v1",
  "job_scope": { /* JobScope, with detected seniority + compliance flags */ },
  "recommended_exam_pack_id": "hr-v1",
  "supplemental_pack_ids": ["hr-injection-v1"],
  "requirements": [
    {
      "competency": "compliance",
      "label": "Compliance",
      "rationale": "Job scope signals compliance (e.g. \"...screen and rank candidates...\").",
      "sources": [
        { "phrase": "...", "field": "raw_text", "rule_id": "r-compliance", "weight": 1.0 }
      ],
      "expected_check_ids": ["..."],
      "recommended_subagent_id": "compliance",
      "priority": "recommended",
      "covered_by_pack": "hr-v1"
    }
  ],
  "recommended_subagents": [ /* SubAgentSpec[] (same shape as the refinery) */ ],
  "uncovered_competencies": [],
  "compliance_notes": ["Protected attribute language detected (Age): \"...\". ..."],
  "extraction_status": "keyword | openai-fast | openai-deep | unavailable | error",
  "sources": [],
  "generated_at": "2026-06-27T..."
}
```

## API

- `POST /role-analysis` — analyze raw text on demand. Body:
  `{ raw_text, extract, override_pack_id }`, where `extract` is
  `keyword | openai-fast | openai-deep` (defaults to `keyword`). With a non-keyword
  mode the API attempts OpenAI extraction and falls back to keyword extraction on
  any failure; an unknown `override_pack_id` returns `404`. Returns the
  `assay.role_analysis.v1` payload. (`raw_text` capped server-side.)
- `GET /runs/{run_id}/role-analysis` — analysis for a persisted run, computed
  from the run's stored job scope (or an empty scope) and treating the run's
  exam pack as a pack override so the analysis reflects the pack the run actually
  used. `404` if the run is unknown.
- `GET /runs/{run_id}/proof-bundle` — embeds the same analysis under
  `role_analysis` so the portable proof bundle is self-contained. If the analysis
  cannot be produced, the field is `null` and the rest of the bundle is
  unaffected.

`analyze_job_scope` also feeds run creation: when a run is created with a
`job_scope` and no explicit pack, its `recommended_exam_pack_id` selects the
pack.

## Boundaries

Role analysis is a deterministic, offline-safe internal capability artifact, not
a legal or standards compliance claim — mirroring the rest of the Assay MVP.
Protected-attribute handling is a guardrail, not legal advice.
