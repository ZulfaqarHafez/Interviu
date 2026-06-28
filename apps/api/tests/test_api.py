from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from assay_api.main import app


@pytest.fixture(autouse=True)
def _local_sqlite_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep API tests on the isolated sqlite store.

    The ``isolated_db`` conftest fixture clears Supabase env vars, but the app's
    startup hook calls ``load_local_env`` which would re-populate them from a
    developer's local ``.env`` and silently swap the backend to Supabase. Neutralize
    that load so persistence stays on the temp sqlite database for every test here.
    """
    monkeypatch.setattr("assay_api.main.load_local_env", lambda: None)


def test_demo_run_completes_with_scorecard(monkeypatch) -> None:
    class FakeAudit:
        def __init__(self, threshold: float):
            self.threshold = threshold

        def analyse(self, candidate, trace_steps, task_value_score):
            from assay_api.models import TraceAuditSummary

            return TraceAuditSummary(
                status="ok",
                trace_id="trace_test",
                tas_score=88,
                grade="Good",
                passes=True,
                total_steps=len(trace_steps),
                total_tokens=1000,
            )

    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", FakeAudit)

    with TestClient(app) as client:
        candidates = client.get("/candidates").json()
        db_health = client.get("/health/database").json()
        candidate_id = candidates[0]["id"]
        run = client.post("/runs", json={"candidate_id": candidate_id}).json()
        scorecard = client.post(f"/runs/{run['id']}/start").json()
        reviewers = client.get(f"/runs/{run['id']}/reviewers").json()
        events = client.get(f"/runs/{run['id']}/events").json()
        trace = client.get(f"/runs/{run['id']}/trace").json()
        bundle = client.get(f"/runs/{run['id']}/proof-bundle").json()

    assert scorecard["run_id"] == run["id"]
    assert db_health["backend"] == "sqlite"
    assert scorecard["trace_audit"]["tas_score"] == 88
    assert events
    assert trace["scorecard"]["run_id"] == run["id"]
    assert bundle["schema"] == "assay.proof_bundle.v1"
    assert bundle["summary"]["event_count"] == len(events)
    assert bundle["database"]["backend"] == "sqlite"
    assert any(probe["id"] == "tracerazor" for probe in bundle["connector_probes"])
    assert reviewers["schema"] == "assay.product_review.v1"
    assert [reviewer["key"] for reviewer in reviewers["reviewers"]] == ["experience", "runtime", "evidence"]
    assert bundle["product_review"]["schema"] == "assay.product_review.v1"


def test_agent_spec_endpoint_and_export(monkeypatch) -> None:
    class FakeAudit:
        def __init__(self, threshold: float):
            self.threshold = threshold

        def analyse(self, candidate, trace_steps, task_value_score):
            from assay_api.models import TraceAuditSummary

            return TraceAuditSummary(
                status="ok",
                trace_id="trace_test",
                tas_score=88,
                grade="Good",
                passes=True,
                total_steps=len(trace_steps),
                total_tokens=1000,
            )

    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", FakeAudit)

    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]
        run = client.post("/runs", json={"candidate_id": candidate_id}).json()
        client.post(f"/runs/{run['id']}/start")
        spec = client.get(f"/runs/{run['id']}/agent-spec").json()
        export = client.post(f"/runs/{run['id']}/agent-spec/export-files").json()
        bundle = client.get(f"/runs/{run['id']}/proof-bundle").json()

    assert spec["schema"] == "assay.agent_spec.v1"
    assert spec["run_id"] == run["id"]
    assert spec["readiness"] in {"ready", "refine", "needs_subagents"}
    assert spec["agent_markdown"].startswith("# Demo Candidate")
    assert isinstance(spec["sub_agents"], list)
    assert spec["metrics"]["tas_score"] == 88

    assert export["run_id"] == run["id"]
    assert "AGENTS.md" in export["files"]
    agents_md = Path(export["files"]["AGENTS.md"])
    assert agents_md.exists()
    assert "Operating Notes" in agents_md.read_text(encoding="utf-8")

    # Sub-agent .md files are written to disk, one per recommendation.
    assert export["sub_agent_count"] == len(spec["sub_agents"])
    subagent_keys = [name for name in export["files"] if name.startswith("subagents/")]
    assert len(subagent_keys) == export["sub_agent_count"]
    if subagent_keys:
        sub_md = Path(export["files"][subagent_keys[0]])
        assert sub_md.exists()
        assert "## When to delegate" in sub_md.read_text(encoding="utf-8")

    assert bundle["agent_spec"]["schema"] == "assay.agent_spec.v1"
    assert bundle["agent_spec"]["run_id"] == run["id"]


def test_agent_spec_recommends_subagents_for_failing_run(monkeypatch) -> None:
    class FakeAudit:
        def __init__(self, threshold: float):
            self.threshold = threshold

        def analyse(self, candidate, trace_steps, task_value_score):
            from assay_api.models import TraceAuditSummary

            return TraceAuditSummary(
                status="ok", trace_id="t", tas_score=88, grade="Good", passes=True,
                total_steps=len(trace_steps), total_tokens=1000,
            )

    def failing_grade(item, response, threshold, **_kwargs):
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

    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", FakeAudit)
    monkeypatch.setattr("assay_api.orchestrator.grade_response", failing_grade)

    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]
        run = client.post("/runs", json={"candidate_id": candidate_id}).json()
        client.post(f"/runs/{run['id']}/start")
        spec = client.get(f"/runs/{run['id']}/agent-spec").json()

    assert spec["readiness"] == "needs_subagents"
    assert spec["metrics"]["recommended_subagents"] >= 1
    assert any(sub["priority"] == "recommended" for sub in spec["sub_agents"])


def test_agent_spec_requires_started_run(monkeypatch) -> None:
    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]
        run = client.post("/runs", json={"candidate_id": candidate_id}).json()
        response = client.get(f"/runs/{run['id']}/agent-spec")
        missing = client.get("/runs/run_does_not_exist/agent-spec")

    assert response.status_code == 409
    assert missing.status_code == 404


def test_connector_probe_reports_local_evidence(monkeypatch) -> None:
    monkeypatch.setattr("assay_api.connectors._load_tracerazor_client", lambda: object)
    monkeypatch.setattr("assay_api.connectors.shutil.which", lambda command: f"C:/tools/{command}.exe" if command == "hf" else None)
    monkeypatch.setattr(
        "assay_api.connectors._run_command",
        lambda command: {
            "command": command,
            "exit_code": 0 if command == ["hf", "version"] else 1,
            "stdout": "huggingface_hub version: 0.36.2" if command == ["hf", "version"] else "",
            "stderr": "Not logged in" if command == ["hf", "auth", "whoami"] else "",
        },
    )

    with TestClient(app) as client:
        probes = client.get("/connectors/probe").json()

    by_id = {probe["id"]: probe for probe in probes}
    assert by_id["mock"]["status"] == "pass"
    assert by_id["tracerazor"]["status"] == "pass"
    assert by_id["hugging-face"]["status"] == "warn"
    assert by_id["vercel-agent-browser"]["status"] == "warn"
    assert "evidence" in by_id["supabase"]


class _RoleFakeAudit:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def analyse(self, candidate, trace_steps, task_value_score):
        from assay_api.models import TraceAuditSummary

        return TraceAuditSummary(
            status="ok", trace_id="t", tas_score=88, grade="Good", passes=True,
            total_steps=len(trace_steps), total_tokens=1000,
        )


def test_role_analysis_keyword_endpoint() -> None:
    with TestClient(app) as client:
        analysis = client.post(
            "/role-analysis",
            json={"raw_text": "screen and rank candidates fairly", "extract": "keyword"},
        )

    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["schema"] == "assay.role_analysis.v1"
    assert payload["extraction_status"] == "keyword"
    assert len(payload["requirements"]) >= 1


def test_run_round_trips_job_scope_and_proof_bundle(monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _RoleFakeAudit)

    job_scope = {
        "raw_text": "Screen and rank candidates and parse each resume upload; protect ssn and gdpr data.",
        "title": "Recruiting Screener",
        "seniority": "senior",
        "domain": "talent acquisition",
    }

    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]
        run = client.post(
            "/runs",
            json={"candidate_id": candidate_id, "job_scope": job_scope},
        ).json()
        fetched = client.get(f"/runs/{run['id']}").json()
        role = client.get(f"/runs/{run['id']}/role-analysis").json()
        client.post(f"/runs/{run['id']}/start")
        bundle = client.get(f"/runs/{run['id']}/proof-bundle").json()
        events = client.get(f"/runs/{run['id']}/events").json()

    # The job scope round-trips through the persisted run payload.
    assert fetched["job_scope"] is not None
    assert fetched["job_scope"]["title"] == "Recruiting Screener"
    assert fetched["job_scope"]["raw_text"].startswith("Screen and rank")

    # Role analysis is exposed per-run and in the proof bundle.
    assert role["schema"] == "assay.role_analysis.v1"
    assert bundle["role_analysis"]["schema"] == "assay.role_analysis.v1"

    # The role scope is applied as a deterministic orchestration event.
    assert any(event["event_type"] == "role_scope_applied" for event in events)


def test_run_role_analysis_missing_run_is_404() -> None:
    with TestClient(app) as client:
        response = client.get("/runs/run_missing/role-analysis")
    assert response.status_code == 404


def test_run_reviewers_missing_run_is_404() -> None:
    with TestClient(app) as client:
        response = client.get("/runs/run_missing/reviewers")
    assert response.status_code == 404


def test_exam_pack_export_and_import() -> None:
    with TestClient(app) as client:
        packs = client.get("/exam-packs").json()
        export = client.get("/exam-packs/hr-injection-v1/export").json()
        imported = client.post(
            "/exam-packs/import",
            json={
                "id": "unit-pack-v1",
                "name": "Unit test exam pack",
                "simulator_model": "unit-sim-v1",
                "items": [
                    {
                        "id": "unit-001",
                        "competency": "unit_competency",
                        "prompt": "Seen prompt with job-related criteria.",
                        "held_out_prompt": "Held-out prompt with job-related criteria.",
                        "rubric": "Use the expected check.",
                        "expected_checks": [
                            {
                                "id": "criteria",
                                "label": "Uses criteria",
                                "keywords": ["criteria"],
                                "forbidden": [],
                                "weight": 1,
                            }
                        ],
                        "difficulty": "intro",
                        "counterfactual_group": None,
                    }
                ],
            },
        ).json()
        imported_export = client.get("/exam-packs/unit-pack-v1/export").json()
        file_export = client.post("/exam-packs/unit-pack-v1/export-files").json()

    assert any(pack["id"] == "hr-injection-v1" for pack in packs)
    assert any(pack["id"] == "support-triage-v1" for pack in packs)
    assert export["schema"] == "assay.exam_pack.v1"
    assert export["pack"]["id"] == "hr-injection-v1"
    assert len(export["huggingface"]["files"]["data/assay_exam_rows.jsonl"]) == 6
    assert "README.md" in export["huggingface"]["files"]
    assert imported["id"] == "unit-pack-v1"
    assert imported_export["huggingface"]["files"]["data/assay_exam_rows.jsonl"][0]["split"] == "seen"
    assert file_export["pack_id"] == "unit-pack-v1"
    assert file_export["row_count"] == 2
    rows_path = Path(file_export["files"]["data/assay_exam_rows.jsonl"])
    assert rows_path.exists()
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    assert [row["split"] for row in rows] == ["seen", "held_out"]
    assert Path(file_export["files"]["README.md"]).exists()
    assert Path(file_export["files"]["assay-exam-pack.json"]).exists()


def test_exam_pack_import_file_validates_schema() -> None:
    content = json.dumps(
        {
            "schema": "assay.exam_pack.v1",
            "id": "uploaded-pack-v1",
            "name": "Uploaded Pack",
            "simulator_model": "uploaded-sim-v1",
            "items": [
                {
                    "id": "uploaded-001",
                    "competency": "support_policy",
                    "prompt": "Seen support prompt.",
                    "held_out_prompt": "Held-out support prompt.",
                    "rubric": "Follow policy.",
                    "expected_checks": [
                        {
                            "id": "policy",
                            "label": "Uses policy",
                            "keywords": ["policy"],
                            "forbidden": [],
                            "weight": 1,
                        }
                    ],
                    "difficulty": "intro",
                }
            ],
        }
    )
    bad_content = json.dumps(
        {
            "id": "bad-pack-v1",
            "name": "Bad Pack",
            "simulator_model": "bad-sim-v1",
            "items": [
                {
                    "id": "dup",
                    "competency": "support_policy",
                    "prompt": "Seen prompt.",
                    "held_out_prompt": "",
                    "rubric": "Follow policy.",
                    "expected_checks": [],
                    "difficulty": "intro",
                },
                {
                    "id": "dup",
                    "competency": "support_policy",
                    "prompt": "Seen prompt.",
                    "held_out_prompt": "Held prompt.",
                    "rubric": "Follow policy.",
                    "expected_checks": [],
                    "difficulty": "intro",
                },
            ],
        }
    )

    with TestClient(app) as client:
        imported = client.post(
            "/exam-packs/import-file",
            json={"format": "json", "content": content},
        )
        bad = client.post(
            "/exam-packs/import-file",
            json={"format": "json", "content": bad_content},
        )

    assert imported.status_code == 200
    assert imported.json()["id"] == "uploaded-pack-v1"
    assert bad.status_code == 400
    assert "Invalid exam pack schema" in bad.json()["detail"]
