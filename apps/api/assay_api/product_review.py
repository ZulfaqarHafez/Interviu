from __future__ import annotations

from typing import Any

from .database import database_health, get_run, get_scorecard, list_events
from .models import ProductReview, ProductReviewer, Scorecard


def product_review_for_run(run_id: str) -> ProductReview | None:
    run = get_run(run_id)
    if run is None:
        return None
    scorecard = get_scorecard(run_id)
    events = list_events(run_id)
    try:
        db = database_health()
    except Exception as exc:
        db = {"ok": False, "backend": "unknown", "error": str(exc)}

    return ProductReview(
        run_id=run_id,
        reviewers=[
            _ux_reviewer(scorecard, len(events)),
            _runtime_reviewer(scorecard, db),
            _evidence_reviewer(scorecard, len(events), db),
        ],
    )


def _ux_reviewer(scorecard: Scorecard | None, event_count: int) -> ProductReviewer:
    if scorecard is None:
        return ProductReviewer(
            key="experience",
            name="UX reviewer",
            status="wait",
            label="ready",
            summary="Evaluation room is ready for a first run.",
            evidence=["No scorecard has been created yet."],
            next_step="Run an evaluation to review the score, proof, and coaching surfaces.",
            sprite="candidate-document",
        )
    if scorecard.certified:
        return ProductReviewer(
            key="experience",
            name="UX reviewer",
            status="pass",
            label="clear",
            summary="Workflow, score, proof, and coaching are visible after the run.",
            evidence=[
                f"{sum(1 for passed in scorecard.pass_at_k.values() if passed)}/{len(scorecard.pass_at_k)} competencies passed.",
                f"{event_count} ordered spans are available for the trace drawer.",
            ],
            sprite="candidate-document",
        )
    return ProductReviewer(
        key="experience",
        name="UX reviewer",
        status="warn",
        label="review",
        summary="The app shows why the run needs review and keeps the next step visible.",
        evidence=scorecard.failure_reasons[:3] or ["The scorecard is not certified."],
        next_step="Use the coaching plan and trace drawer to resolve review reasons.",
        sprite="candidate-review",
    )


def _runtime_reviewer(scorecard: Scorecard | None, db: dict[str, Any]) -> ProductReviewer:
    trace = scorecard.trace_audit if scorecard else None
    if not db.get("ok", False):
        return ProductReviewer(
            key="runtime",
            name="Runtime reviewer",
            status="warn",
            label="check",
            summary="Database health needs attention.",
            evidence=[str(db.get("error") or "Database health returned not ok.")],
            next_step="Check the API database configuration before relying on persisted runs.",
            sprite="candidate-alert",
        )
    if trace and trace.status != "ok":
        return ProductReviewer(
            key="runtime",
            name="Runtime reviewer",
            status="warn",
            label="check",
            summary="TraceRazor needs attention before this run can certify.",
            evidence=[trace.message or f"TraceRazor status is {trace.status}."],
            next_step="Check TraceRazor installation, timeout, and candidate-only audit steps.",
            sprite="candidate-alert",
        )
    return ProductReviewer(
        key="runtime",
        name="Runtime reviewer",
        status="pass",
        label="stable",
        summary=f"{db.get('backend', 'sqlite')} storage is responding.",
        evidence=[f"Database backend: {db.get('backend', 'unknown')}."],
        sprite="candidate-shield",
    )


def _evidence_reviewer(scorecard: Scorecard | None, event_count: int, db: dict[str, Any]) -> ProductReviewer:
    if scorecard is None:
        return ProductReviewer(
            key="evidence",
            name="Evidence reviewer",
            status="wait",
            label="waiting",
            summary="Waiting for a scorecard and proof bundle.",
            evidence=["No completed run is available yet."],
            next_step="Run an evaluation to create scorecard and trace evidence.",
            sprite="candidate-audit",
        )
    if scorecard.certified and scorecard.trace_audit.status == "ok" and event_count > 0:
        return ProductReviewer(
            key="evidence",
            name="Evidence reviewer",
            status="pass",
            label="passed",
            summary="Proof bundle, trace events, and audit summary support the result.",
            evidence=[
                f"TraceRazor TAS {scorecard.trace_audit.tas_score:.1f}.",
                f"{event_count} events persisted in {db.get('backend', 'storage')}.",
            ],
            sprite="candidate-approved",
        )
    return ProductReviewer(
        key="evidence",
        name="Evidence reviewer",
        status="warn",
        label="review",
        summary="Proof bundle records the review reasons.",
        evidence=scorecard.failure_reasons[:3] or ["Run evidence exists but certification is not complete."],
        next_step="Open the trace drawer and address the failing proof requirement.",
        sprite="candidate-review",
    )
