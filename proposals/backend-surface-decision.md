# Proposal: Decide Hidden Backend Surfaces

## Problem
Several backend capabilities remain after the cockpit UI was removed: HTTP
candidates, role analysis, HF export, and OpenAI research. Hidden endpoints
increase maintenance and security surface unless they are intentionally exposed.

## Options
- Re-expose the surfaces in `/agents` and `/suites` with clear affordances.
- Keep only the surfaces needed by the current Assay flow and delete the rest.
- Keep server-only/internal surfaces but require API keys and document them as
  unsupported UI paths.

## Recommendation
Re-expose only the parts that directly support the current product promise:
suite import/export, role scope analysis, and proof-bundle research. Keep HTTP
candidates, but present them as an advanced local-only integration with the SSRF
guard enabled by default.

## Acceptance Sketch
- Every retained endpoint has a UI path, doc entry, or explicit internal label.
- Every deleted endpoint has a migration note or test removal in the same PR.
