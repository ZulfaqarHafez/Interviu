"""Read-side aggregation for the diagnostic library and candidate progress.

All functions here are deterministic and rely only on persisted runs,
scorecards, and lessons — no LLM calls. They turn the closed learning loop
(see ``orchestrator.py``) into observable progress: per-competency trends over
time, run-to-run comparisons, and the live lesson library.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from .database import (
    get_candidate,
    get_lesson,
    get_run,
    get_scorecard,
    list_lessons_for_candidate,
    list_runs_for_candidate,
)
from .models import (
    CandidateProgress,
    CompetencyComparison,
    CompetencyProgress,
    CompetencyTrendPoint,
    DiagnosticLesson,
    RunComparison,
    Scorecard,
)

_IMPROVE_BAND = 0.05


def _labelize(value: str) -> str:
    return value.replace("_", " ").title()


def _competency_lesson_counts(scorecard: Scorecard) -> dict[str, int]:
    """Resolve a scorecard's applied lesson ids to per-competency counts."""
    counts: dict[str, int] = defaultdict(int)
    for lesson_id in scorecard.lessons_applied:
        lesson = get_lesson(lesson_id)
        if lesson is not None:
            counts[lesson.competency] += 1
    return counts


def _trend(first: float | None, latest: float | None, point_count: int) -> Literal["improving", "regressing", "flat", "insufficient"]:
    if point_count < 2 or first is None or latest is None:
        return "insufficient"
    delta = latest - first
    if delta >= _IMPROVE_BAND:
        return "improving"
    if delta <= -_IMPROVE_BAND:
        return "regressing"
    return "flat"


def candidate_progress(candidate_id: str) -> CandidateProgress | None:
    """Per-candidate competency trends, pass rate, and active-lesson count."""
    candidate = get_candidate(candidate_id)
    if candidate is None:
        return None

    runs = [run for run in list_runs_for_candidate(candidate_id) if run.status == "completed"]
    points_by_comp: dict[str, list[CompetencyTrendPoint]] = defaultdict(list)
    certified_count = 0
    for run in runs:
        scorecard = get_scorecard(run.id)
        if scorecard is None:
            continue
        if scorecard.certified:
            certified_count += 1
        lesson_counts = _competency_lesson_counts(scorecard)
        for competency, score in scorecard.held_out_scores.items():
            points_by_comp[competency].append(
                CompetencyTrendPoint(
                    run_id=run.id,
                    created_at=scorecard.created_at,
                    held_out_score=score,
                    passed=scorecard.pass_at_k.get(competency, False),
                    transfer_gap=scorecard.transfer_gap.get(competency, 0.0),
                    lessons_applied=lesson_counts.get(competency, 0),
                )
            )

    active_lessons = list_lessons_for_candidate(candidate_id, active_only=True)
    active_by_comp: dict[str, int] = defaultdict(int)
    for lesson in active_lessons:
        active_by_comp[lesson.competency] += 1

    competencies: list[CompetencyProgress] = []
    for competency in sorted(points_by_comp):
        points = points_by_comp[competency]
        first = points[0].held_out_score if points else None
        latest = points[-1].held_out_score if points else None
        competencies.append(
            CompetencyProgress(
                competency=competency,
                label=_labelize(competency),
                points=points,
                first_score=first,
                latest_score=latest,
                delta=round(latest - first, 3) if first is not None and latest is not None else None,
                trend=_trend(first, latest, len(points)),
                active_lessons=active_by_comp.get(competency, 0),
            )
        )

    pass_rate = round(certified_count / len(runs), 3) if runs else 0.0
    return CandidateProgress(
        candidate_id=candidate_id,
        candidate_name=candidate.name,
        run_count=len(runs),
        pass_rate=pass_rate,
        competencies=competencies,
        runs=runs,
        active_lessons=len(active_lessons),
    )


def run_comparison(run_id: str, baseline_run_id: str | None = None) -> RunComparison | None:
    """Diff a run's held-out competency scores against a baseline run.

    The baseline defaults to the run's recorded ``prior_run_id`` (the candidate's
    previous completed run on the same pack), so the common case needs no args.
    """
    run = get_run(run_id)
    if run is None:
        return None
    current = get_scorecard(run_id)
    if current is None:
        return None

    baseline_id = baseline_run_id or current.prior_run_id
    baseline = get_scorecard(baseline_id) if baseline_id else None

    competency_names = sorted(set(current.held_out_scores) | set(baseline.held_out_scores if baseline else {}))
    comparisons: list[CompetencyComparison] = []
    improved = regressed = unchanged = 0
    for competency in competency_names:
        current_score = current.held_out_scores.get(competency)
        baseline_score = baseline.held_out_scores.get(competency) if baseline else None
        if current_score is not None and baseline_score is not None:
            delta = round(current_score - baseline_score, 3)
            if delta >= _IMPROVE_BAND:
                outcome: Literal["improved", "regressed", "unchanged", "new", "dropped"] = "improved"
                improved += 1
            elif delta <= -_IMPROVE_BAND:
                outcome = "regressed"
                regressed += 1
            else:
                outcome = "unchanged"
                unchanged += 1
        elif current_score is not None:
            delta = None
            outcome = "new"
        else:
            delta = None
            outcome = "dropped"
        comparisons.append(
            CompetencyComparison(
                competency=competency,
                label=_labelize(competency),
                baseline_score=baseline_score,
                current_score=current_score,
                delta=delta,
                outcome=outcome,
                baseline_passed=baseline.pass_at_k.get(competency) if baseline else None,
                current_passed=current.pass_at_k.get(competency),
            )
        )

    certified_changed = bool(baseline) and baseline.certified != current.certified
    return RunComparison(
        run_id=run_id,
        baseline_run_id=baseline_id,
        candidate_id=run.candidate_id,
        competencies=comparisons,
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        certified_changed=certified_changed,
    )


def lesson_library(candidate_id: str, exam_pack_id: str | None = None) -> list[DiagnosticLesson]:
    """All retained lessons (active and retired) for a candidate."""
    return list_lessons_for_candidate(candidate_id, exam_pack_id, active_only=False)
