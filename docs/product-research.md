# Product Research Notes

Assay should stay focused on local, inspectable agent evaluation instead of becoming a generic observability dashboard.

## Adversarial Exam Shape

AgentDojo is the closest public inspiration for the dojo framing: benchmark tasks are built around agents facing adversarial instructions in realistic tool-using environments. Assay adapts that idea to HR screening by keeping a seen prompt, held-out prompt, rubric, expected checks, and counterfactual protected-attribute group on every `ExamItem`.

Source: https://github.com/ethz-spylab/agentdojo

## Dataset Export Shape

Hugging Face dataset repos are a natural public handoff target for Assay exam packs. The app exports each pack as `assay.exam_pack.v1` with a generated dataset card and JSONL rows under `data/assay_exam_rows.jsonl`, so the first useful Hub workflow is auth-gated upload rather than a custom hosted sync service.

Source: https://huggingface.co/docs/hub/datasets-cards

## Supabase Boundary

Supabase remains a server-side persistence connector for candidates, runs, scorecards, and trace spans. The frontend must never receive a service-role key; browser code talks only to the Assay API, and the API decides whether to use SQLite fallback or Supabase based on server-only environment variables.

Source: https://supabase.com/docs/guides/database/postgres/row-level-security

## Current Product Consequence

The MVP keeps three surfaces visible on the first screen:

- Run setup: select a candidate and exam pack, with HTTP setup available only when opened.
- Score: show internal capability bars without claiming legal or standards compliance.
- Proof: expose TraceRazor status, transfer gap, trace view, and proof export.

Everything else stays quieter: exam export, previous runs, connector probes, and debug spans are collapsed so Assay reads as a real evaluation product rather than an internal benchmark console.

## Candidate On-Ramp

AgentDojo's public shape reinforces the need for realistic adversarial agent evaluation instead of a static checklist. Assay's matching product move is to make the candidate boundary black-box and easy to exercise: the local HTTP starter in `examples/http_candidate` implements the production adapter contract, so a user can swap the example endpoint for a real model or agent without changing the examiner or proof path.
