# Proposal: Exam Pack Expansion

## Problem
The current HR-focused packs are a credible demo but too narrow for broader
agent-vetting use.

## Shape
- Define a user-uploadable YAML/JSON pack format with schema validation.
- Add at least one non-HR domain pack, such as support triage, code generation,
  or data-access safety.
- Keep generated Hugging Face export files compatible with the existing export
  flow.

## Guardrails
- Validate IDs, prompt lengths, expected checks, weights, and forbidden terms.
- Reject packs that contain empty held-out prompts or duplicate item IDs.
- Version pack schemas so future fields do not silently change scoring.

## Acceptance Sketch
- A sample non-HR pack imports, exports, runs, and appears in `/suites`.
- Invalid packs fail with actionable 400/422 errors.
