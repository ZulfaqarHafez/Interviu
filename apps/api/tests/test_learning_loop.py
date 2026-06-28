from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from assay_api.main import app


@pytest.fixture(autouse=True)
def _local_sqlite_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mirror test_api.py: keep the learning-loop tests on the isolated sqlite
    # store and stop startup from re-loading a developer's local .env.
    monkeypatch.setattr("assay_api.main.load_local_env", lambda: None)


class _FakeAudit:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def analyse(self, candidate, trace_steps, task_value_score):
        from assay_api.models import TraceAuditSummary

        return TraceAuditSummary(
            status="ok", trace_id="t", tas_score=88, grade="Good", passes=True,
            total_steps=len(trace_steps), total_tokens=1000,
        )


def _failing_grade(item, response, threshold, **_kwargs):
    from assay_api.scoring import GradeResult

    return GradeResult(
        score=0.2,
        passed=False,
        panel_scores={"rubric": 0.2, "compliance": 0.2, "consistency": 0.2},
        matched_checks=[],
        missed_checks=[check.id for check in item.expected_checks],
        forbidden_hits=[],
        feedback="needs work",
    )


def _passing_grade(item, response, threshold, **_kwargs):
    from assay_api.scoring import GradeResult

    return GradeResult(
        score=0.95,
        passed=True,
        panel_scores={"rubric": 0.95, "compliance": 0.95, "consistency": 0.95},
        matched_checks=[check.id for check in item.expected_checks],
        missed_checks=[],
        forbidden_hits=[],
        feedback="great",
    )


def _start_run(client: TestClient, candidate_id: str) -> str:
    run = client.post("/runs", json={"candidate_id": candidate_id}).json()
    client.post(f"/runs/{run['id']}/start")
    return run["id"]


def test_lessons_persist_and_apply_across_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    monkeypatch.setattr("assay_api.orchestrator.grade_response", _failing_grade)

    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]

        # Run A: every competency fails, so the diagnostic library is seeded.
        run_a = _start_run(client, candidate_id)
        lessons_after_a = client.get(f"/candidates/{candidate_id}/lessons").json()
        assert lessons_after_a, "run A should persist at least one diagnostic lesson"
        a_origin_run_ids = {lesson["origin_run_id"] for lesson in lessons_after_a}
        assert a_origin_run_ids == {run_a}

        # Run B: same candidate + pack. Prior lessons must be applied.
        run_b = _start_run(client, candidate_id)
        scorecard_b = client.get(f"/runs/{run_b}/scorecard").json()
        events_b = client.get(f"/runs/{run_b}/events").json()
        applied = client.get(f"/runs/{run_b}/lessons-applied").json()

    # The scorecard records which library lessons it consumed and its baseline.
    assert scorecard_b["lessons_applied"], "run B should apply prior-run lessons"
    assert scorecard_b["prior_run_id"] == run_a
    # The timeline shows the application event.
    assert any(event["event_type"] == "lesson_applied" for event in events_b)
    # Applied lessons resolve and now record run B in their provenance.
    assert applied
    assert all(run_b in lesson["applied_run_ids"] for lesson in applied)
    assert all(lesson["latest_outcome"] == "still_failing" for lesson in applied)

    # Idempotency: re-running the same failure does not duplicate lesson rows.
    with TestClient(app) as client:
        lessons_after_b = client.get(f"/candidates/{candidate_id}/lessons").json()
    assert len(lessons_after_b) == len(lessons_after_a)


def test_progress_tracks_competency_trend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)

    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]

        # Run A fails the competencies (creates lessons with a low origin score).
        monkeypatch.setattr("assay_api.orchestrator.grade_response", _failing_grade)
        run_a = _start_run(client, candidate_id)

        # Run B recovers: the competencies now pass.
        monkeypatch.setattr("assay_api.orchestrator.grade_response", _passing_grade)
        run_b = _start_run(client, candidate_id)

        progress = client.get(f"/candidates/{candidate_id}/progress").json()
        comparison = client.get(f"/runs/{run_b}/comparison?baseline={run_a}").json()
        lessons = client.get(f"/candidates/{candidate_id}/lessons").json()

    assert progress["schema"] == "assay.candidate_progress.v1"
    assert progress["run_count"] == 2
    assert progress["competencies"], "progress should report per-competency trends"
    a_competency = progress["competencies"][0]
    assert len(a_competency["points"]) >= 2
    assert a_competency["delta"] is not None
    assert a_competency["trend"] == "improving"

    # The run comparison shows the recovery as an improvement vs the baseline.
    assert comparison["schema"] == "assay.run_comparison.v1"
    assert comparison["baseline_run_id"] == run_a
    assert comparison["improved"] >= 1

    # Recovered lessons are marked improved and retired from the active library.
    assert any(lesson["latest_outcome"] == "improved" for lesson in lessons)
    assert all(lesson["active"] is False for lesson in lessons)


def test_progress_404_for_unknown_candidate() -> None:
    with TestClient(app) as client:
        assert client.get("/candidates/cand_missing/progress").status_code == 404
        assert client.get("/candidates/cand_missing/lessons").status_code == 404
