from __future__ import annotations

from assay_api.models import CandidateConfig
from assay_api.trace_audit import TraceAuditService, _audit_slice


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

    monkeypatch.setattr("assay_api.trace_audit._load_tracerazor_client", lambda: FakeClient)

    service = TraceAuditService(threshold=70)
    candidate = CandidateConfig(name="Demo", adapter_type="mock")
    steps = [{"id": index + 1, "type": "reasoning", "content": "x", "tokens": 1} for index in range(5)]

    summary = service.analyse(candidate, trace_steps=steps, task_value_score=0.9)

    assert summary.status == "ok"
    assert summary.tas_score == 91.0
    assert summary.savings["tokens_saved"] == 12


def test_trace_audit_caps_large_repeated_traces(monkeypatch) -> None:
    class FakeReport:
        trace_id = "trace_sampled"
        tas_score = 84.0
        grade = "Good"
        passes = True
        total_steps = 8
        total_tokens = 800
        metrics = {"score": 84}
        savings = {}
        fixes = []
        raw = {"ok": True}

    class FakeClient:
        def __init__(self, threshold: float):
            self.threshold = threshold

        def analyse(self, trace):
            assert len(trace["steps"]) == 8
            assert trace["metadata"]["source_steps"] == 60
            assert trace["metadata"]["audited_steps"] == 8
            assert trace["metadata"]["sampling"] == "representative"
            return FakeReport()

    monkeypatch.setattr("assay_api.trace_audit._load_tracerazor_client", lambda: FakeClient)

    service = TraceAuditService(threshold=70)
    candidate = CandidateConfig(name="Demo", adapter_type="mock")
    steps = [
        {
            "id": index + 1,
            "type": "reasoning" if index % 2 == 0 else "tool_call",
            "content": f"step {index}",
            "tokens": 40,
            "metadata": {
                "competency": f"comp_{index % 5}",
                "variant": "seen" if index % 2 == 0 else "held_out",
            },
        }
        for index in range(60)
    ]

    summary = service.analyse(candidate, trace_steps=steps, task_value_score=1.0)

    assert summary.status == "ok"
    assert summary.total_steps == 60
    assert summary.raw["assay_audit"]["audited_steps"] == 8


def test_audit_slice_keeps_short_traces_unchanged() -> None:
    steps = [{"id": index} for index in range(7)]

    assert _audit_slice(steps, 24) == steps
