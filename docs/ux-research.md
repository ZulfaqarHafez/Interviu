# Assay UX Research Notes

## Comparable Product Patterns

- LangSmith frames evaluation as a workflow: create a dataset, define evaluators, run an experiment, then inspect traces and scores. It also emphasizes side-by-side experiment comparison.
- Braintrust presents evaluations as immutable experiment snapshots, with datasets, scorers, logs, and production feedback using one shared structure.
- Langfuse puts datasets, experiments, prompt versions, traces, and evaluation methods into the same lifecycle so teams can compare versions and trace failures.
- Promptfoo leads with automated evals, red teaming, reports, provider comparison, and CI checks.

## Direction For Assay

Assay should feel like a local evaluation console, not a landing page or arcade. The first screen should answer:

- What candidate and exam pack are being tested?
- Did the current run pass the internal gate?
- Which proof supports that result?
- What should be improved or delegated next?

## Applied UI Decisions

- Replace the large room-first layout with a run cockpit.
- Promote outcome, TraceRazor score, transfer gap, and storage into KPI tiles.
- Keep sprites as compact status markers, not the dominant visual system.
- Keep setup, score, proof, reviewers, and coaching in one right-side inspection column.
- Make the workflow strip read like dataset to experiment to judge to coaching.

## Sources

- LangSmith Evaluation: https://docs.langchain.com/langsmith/evaluation
- LangSmith Evaluation Concepts: https://docs.langchain.com/langsmith/evaluation-concepts
- Braintrust Create Experiments: https://www.braintrust.dev/docs/evaluate/run-evaluations
- Braintrust Observe: https://www.braintrust.dev/docs/observe
- Braintrust Datasets: https://www.braintrust.dev/docs/annotate/datasets
- Langfuse Datasets: https://langfuse.com/docs/evaluation/experiments/datasets
- Langfuse Experiments via UI: https://langfuse.com/docs/evaluation/experiments/experiments-via-ui
- Promptfoo Intro: https://www.promptfoo.dev/docs/intro/
- Promptfoo Red Teaming: https://www.promptfoo.dev/docs/red-team/
