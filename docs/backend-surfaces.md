# Backend Surfaces

Assay keeps a few backend capabilities that are not part of the single-screen
Assay intake. Each retained surface has a product path, a documentation path, or
an explicit internal label.

## Product UI Paths

| Capability | API | UI path | Status |
| --- | --- | --- | --- |
| Agent markdown intake | `POST /candidates/from-markdown` | `/` | Primary Assay flow |
| Suite list | `GET /exam-packs` | `/suites` | Visible |
| Suite JSON/YAML import | `POST /exam-packs/import-file` | `/suites` import button | Visible |
| Suite export | `GET /exam-packs/{pack_id}/export` | `/suites` export action | Visible |
| Runs, proof, traces | `GET /runs`, `/runs/{id}/proof-bundle`, `/runs/{id}/trace` | `/runs`, `/runs/{id}` | Visible |
| Agent spec export/research | `/runs/{id}/agent-spec*` | Run detail trace drawer / proof bundle | Visible |
| Role scope analysis | `POST /role-analysis`, `GET /runs/{id}/role-analysis` | Main Assay run + proof bundle | Supported |

## Advanced Local Integration

HTTP candidates remain supported through `POST /candidates` with
`adapter_type=http`. This is an advanced/local integration: endpoint URLs are
validated by the SSRF guard, and private/loopback targets are blocked unless
`ASSAY_HTTP_CANDIDATE_ALLOW_PRIVATE=1` is explicitly set for a trusted local
harness.

## Internal Or Server-Only

OpenAI research, OpenAI role extraction, Supabase persistence, and TraceRazor
audit execution are server-only surfaces. They are invoked by API routes, never
from browser-held secrets, and are included in proof bundles when available.

Hosted multi-tenant mode is opt-in with `ASSAY_REQUIRE_TENANT=1`. In that
mode non-health routes require both `X-API-Key` and `X-Assay-Tenant`; stored
candidates, runs, events, scorecards, lessons, and proof bundles are scoped by
tenant id.
