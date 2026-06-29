from __future__ import annotations

import asyncio

import pytest

from assay_api import orchestrator as orch
from assay_api.models import CandidateConfig, CandidateResponse, RunRecord, TokenCounts, TraceAuditSummary


class _FakeAudit:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def analyse(self, candidate, trace_steps, task_value_score):
        return TraceAuditSummary(status="ok", trace_id="t", tas_score=88, grade="Good",
                                 passes=True, total_steps=len(trace_steps), total_tokens=100)


class _CountingAdapter:
    """Records peak concurrent ask() calls so we can prove items run in parallel."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    async def ask(self, context: str, question: str) -> CandidateResponse:
        self.current += 1
        self.peak = max(self.peak, self.current)
        await asyncio.sleep(0.02)  # hold the slot so overlap is observable
        self.current -= 1
        return CandidateResponse(
            answer="Use job-related skills criteria; refuse protected traits; redact; escalate; untrusted input.",
            tokens=TokenCounts(total=12),
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_items_execute_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSAY_RUN_CONCURRENCY", "5")
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    from assay_api.database import init_db
    init_db()
    adapter = _CountingAdapter()
    monkeypatch.setattr(orch, "adapter_for", lambda candidate: adapter)

    run = RunRecord(candidate_id="c", exam_pack_id="hr-v1", k=2)  # 5 items x 2 trials = 10 units
    candidate = CandidateConfig(id="c", name="x", adapter_type="mock")
    scorecard = await orch.RunOrchestrator().start(run, candidate)

    # The exam ran in parallel (sequential would peak at 1) and still produced a scorecard.
    assert adapter.peak >= 2
    assert scorecard.run_id == run.id
    assert scorecard.competency_scores


@pytest.mark.asyncio
async def test_run_concurrency_one_is_sequential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSAY_RUN_CONCURRENCY", "1")
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    from assay_api.database import init_db
    init_db()
    adapter = _CountingAdapter()
    monkeypatch.setattr(orch, "adapter_for", lambda candidate: adapter)

    run = RunRecord(candidate_id="c", exam_pack_id="hr-v1", k=1)
    candidate = CandidateConfig(id="c", name="x", adapter_type="mock")
    await orch.RunOrchestrator().start(run, candidate)

    assert adapter.peak == 1  # concurrency=1 restores fully-sequential behavior
