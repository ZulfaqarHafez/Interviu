from __future__ import annotations

import os
import sys
from multiprocessing import get_context
from queue import Empty
from typing import Any
from uuid import uuid4

from .models import CandidateConfig, TraceAuditSummary


LOCAL_TRACERAZOR = os.environ.get("TRACERAZOR_REPO", r"C:\Users\zulfa\TraceRazor")


class TraceAuditService:
    DEFAULT_MAX_AUDIT_STEPS = 8

    def __init__(self, threshold: float):
        self.threshold = threshold
        self.timeout_s = float(os.environ.get("ASSAY_TRACERAZOR_TIMEOUT_S", "12"))
        self.max_audit_steps = int(os.environ.get("ASSAY_TRACERAZOR_MAX_STEPS", str(self.DEFAULT_MAX_AUDIT_STEPS)))

    def analyse(
        self,
        candidate: CandidateConfig,
        trace_steps: list[dict[str, Any]],
        task_value_score: float,
    ) -> TraceAuditSummary:
        source_step_count = len(trace_steps)
        if source_step_count < 5:
            return TraceAuditSummary(
                status="insufficient_steps",
                total_steps=source_step_count,
                passes=False,
                message="TraceRazor requires at least 5 candidate steps for this audit.",
            )

        client_cls = _load_tracerazor_client()
        if client_cls is None:
            return TraceAuditSummary(
                status="unavailable",
                total_steps=source_step_count,
                passes=False,
                message="TraceRazor is not importable. Install the local checkout or tracerazor>=1.0.3.",
            )

        audit_steps = _audit_slice(trace_steps, self.max_audit_steps)
        trace = {
            "trace_id": f"assay_{uuid4().hex[:12]}",
            "agent_name": candidate.name,
            "framework": candidate.adapter_type,
            "task_value_score": max(0.0, min(1.0, task_value_score)),
            "steps": audit_steps,
            "metadata": {
                "source_steps": source_step_count,
                "audited_steps": len(audit_steps),
                "sampling": "representative" if len(audit_steps) < source_step_count else "full",
            },
        }
        try:
            report_payload = (
                _analyse_real_client_with_timeout(self.threshold, trace, self.timeout_s)
                if str(getattr(client_cls, "__module__", "")).startswith("tracerazor")
                else _report_payload(client_cls(threshold=self.threshold).analyse(trace))
            )
        except Exception as exc:  # TraceRazor can fail if its CLI is not present.
            return TraceAuditSummary(
                status="error",
                total_steps=source_step_count,
                passes=False,
                raw={"assay_audit": trace["metadata"]},
                message=str(exc),
            )

        raw = dict(report_payload["raw"] or {})
        raw.setdefault("assay_audit", trace["metadata"])
        return TraceAuditSummary(
            status="ok",
            trace_id=report_payload["trace_id"],
            tas_score=report_payload["tas_score"],
            grade=report_payload["grade"],
            passes=report_payload["passes"],
            total_steps=source_step_count,
            total_tokens=report_payload["total_tokens"],
            metrics=report_payload["metrics"],
            savings=report_payload["savings"],
            fixes=report_payload["fixes"],
            raw=raw,
        )


def _load_tracerazor_client() -> Any | None:
    try:
        from tracerazor import TraceRazorClient

        return TraceRazorClient
    except Exception:
        if os.path.isdir(LOCAL_TRACERAZOR) and LOCAL_TRACERAZOR not in sys.path:
            sys.path.insert(0, LOCAL_TRACERAZOR)
        try:
            from tracerazor import TraceRazorClient

            return TraceRazorClient
        except Exception:
            return None


def _analyse_real_client_with_timeout(threshold: float, trace: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    context = get_context("spawn")
    queue = context.Queue(maxsize=1)
    process = context.Process(target=_trace_audit_worker, args=(threshold, trace, queue))
    process.start()
    process.join(timeout_s)
    if process.is_alive():
        process.terminate()
        process.join(2)
        raise TimeoutError(f"TraceRazor audit timed out after {timeout_s:.1f}s.")
    try:
        status, payload = queue.get_nowait()
    except Empty as exc:
        raise RuntimeError("TraceRazor audit exited without returning a report.") from exc
    if status == "error":
        raise RuntimeError(str(payload))
    return payload


def _trace_audit_worker(threshold: float, trace: dict[str, Any], queue: Any) -> None:
    try:
        client_cls = _load_tracerazor_client()
        if client_cls is None:
            raise RuntimeError("TraceRazor is not importable in audit worker.")
        report = client_cls(threshold=threshold).analyse(trace)
        queue.put(("ok", _report_payload(report)))
    except Exception as exc:
        queue.put(("error", str(exc)))


def _audit_slice(trace_steps: list[dict[str, Any]], max_steps: int) -> list[dict[str, Any]]:
    """Return a bounded, ordered, representative candidate trace.

    Assay stores every span, but repeated pass^k variants can produce many
    near-identical candidate steps. TraceRazor only needs enough candidate-only
    reasoning/tool material to score adequacy, so keep a balanced slice while
    avoiding local binary timeouts on routine demos.
    """
    if max_steps <= 0 or len(trace_steps) <= max_steps:
        return trace_steps

    chosen: dict[int, dict[str, Any]] = {}

    def add(index: int) -> None:
        if 0 <= index < len(trace_steps):
            chosen[index] = trace_steps[index]

    # Preserve startup context and final behavior.
    for index in range(min(4, len(trace_steps))):
        add(index)
    for index in range(max(0, len(trace_steps) - 4), len(trace_steps)):
        add(index)

    # Cover each competency/variant pair when metadata is present.
    seen_keys: set[tuple[str, str, str]] = set()
    for index, step in enumerate(trace_steps):
        metadata = step.get("metadata") if isinstance(step, dict) else {}
        if not isinstance(metadata, dict):
            metadata = {}
        key = (
            str(metadata.get("competency", "")),
            str(metadata.get("variant", "")),
            str(step.get("type", "")),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            add(index)
        if len(chosen) >= max_steps:
            break

    # Fill remaining slots evenly through the trace.
    remaining = max_steps - len(chosen)
    if remaining > 0:
        stride = max(1, len(trace_steps) // remaining)
        for index in range(0, len(trace_steps), stride):
            add(index)
            if len(chosen) >= max_steps:
                break
    if len(chosen) < max_steps:
        for index in range(len(trace_steps)):
            add(index)
            if len(chosen) >= max_steps:
                break

    return [trace_steps[index] for index in sorted(chosen)[:max_steps]]


def _report_payload(report: Any) -> dict[str, Any]:
    return {
        "trace_id": report.trace_id,
        "tas_score": report.tas_score,
        "grade": report.grade,
        "passes": report.passes,
        "total_steps": report.total_steps,
        "total_tokens": report.total_tokens,
        "metrics": report.metrics,
        "savings": report.savings,
        "fixes": report.fixes,
        "raw": report.raw,
    }
