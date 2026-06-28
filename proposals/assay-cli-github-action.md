# Proposal: assay-cli and GitHub Action

## Problem
Assay is useful as a local harness, but it becomes sticky only when teams can run
it in CI and block regressions before merge.

## Shape
- Add `assay run --agent-md <file> --pack <id> --pass-threshold <0..1>`.
- Return non-zero when the scorecard fails the threshold or the run errors.
- Emit a machine-readable scorecard JSON path and a short Markdown summary.
- Add a GitHub Action that starts the API/web test harness, runs the CLI, and
  comments the scorecard on pull requests.

## Open Questions
- Should the CLI call the existing FastAPI service, or embed the orchestration
  code directly for single-process CI?
- How should live LLM degradation be represented in a required status check?
- Which artifact should be canonical: scorecard JSON, proof bundle, or both?

## Acceptance Sketch
- `assay run` exits 0 for a passing deterministic mock run and 1 for a failing
  scorecard.
- The Action uploads the proof bundle and comments a compact verdict table.
- Hosted secrets are read from CI env only; no `.env` files are required.
