# Proposal: LLM-Judge Scoring Fallback

## Problem
The current rubric is deterministic and auditable, but keyword checks can miss
valid paraphrases and over-penalize concise answers.

## Shape
- Keep deterministic rubric scoring as the default and source of truth.
- Add an optional semantic judge for sampled responses or disputed scores.
- Store judge prompt, model, raw verdict, confidence, and token usage in the
  proof bundle so semantic scoring remains inspectable.

## Guardrails
- Never let the judge replace hard forbidden checks for protected-trait or
  policy violations.
- Require structured output with a bounded schema.
- Mark scorecards that include judge assistance so users can distinguish
  deterministic and semantic evidence.

## Acceptance Sketch
- A feature flag enables the judge path without changing default test results.
- Golden fixtures cover paraphrase rescue, forbidden-content refusal, and judge
  unavailability fallback.
