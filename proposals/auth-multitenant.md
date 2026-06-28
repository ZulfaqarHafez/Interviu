# Proposal: Auth and Multi-Tenant Scope

## Problem
The API is single-tenant and shared-key oriented. That is acceptable for a local
developer tool, but insufficient for hosting Assay for multiple organizations.

## Shape
- If hosted, add real users, organizations, and run ownership.
- Scope candidates, runs, proof bundles, lessons, and exports by tenant.
- Keep local single-user mode frictionless with no account requirement.

## Guardrails
- Do not retrofit multi-tenant checks piecemeal; define ownership at the data
  model boundary first.
- Treat proof bundles and candidate prompts as sensitive customer data.
- Require API-key or session auth for all non-health hosted endpoints.

## Acceptance Sketch
- A user cannot list, fetch, export, or compare another tenant's runs.
- Existing local tests still pass with auth disabled in development mode.
