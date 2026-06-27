from __future__ import annotations

from interviu_api.models import CandidateConfig
from interviu_api.trace_audit import TraceAuditService


def test_trace_audit_reports_insufficient_steps() -> None:
    service = TraceAuditService(threshold=70)
    candidate = CandidateConfig(name="Demo", adapter_type="mock")

    summary = service.analyse(candidate, trace_steps=[{"id": 1}], task_value_score=1.0)

    assert summary.status == "insufficient_steps"
    assert summary.total_steps == 1
    assert not summary.passes


def test_trace_audit_accepts_fake_client(monkeypatch) -> None:
    class FakeReport:
        trace_id = "trace_fake"
        tas_score = 91.0
        grade = "Excellent"
        passes = True
        total_steps = 5
        total_tokens = 500
        metrics = {"score": 91}
        savings = {"tokens_saved": 12}
        fixes = []
        raw = {"ok": True}

    class FakeClient:
        def __init__(self, threshold: float):
            self.threshold = threshold

        def analyse(self, trace):
            assert len(trace["steps"]) == 5
            assert trace["task_value_score"] == 0.9
            return FakeReport()

    monkeypatch.setattr("interviu_api.trace_audit._load_tracerazor_client", lambda: FakeClient)

    service = TraceAuditService(threshold=70)
    candidate = CandidateConfig(name="Demo", adapter_type="mock")
    steps = [{"id": index + 1, "type": "reasoning", "content": "x", "tokens": 1} for index in range(5)]

    summary = service.analyse(candidate, trace_steps=steps, task_value_score=0.9)

    assert summary.status == "ok"
    assert summary.tas_score == 91.0
    assert summary.savings["tokens_saved"] == 12
