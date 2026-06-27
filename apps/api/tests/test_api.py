from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from interviu_api.main import app


def test_demo_run_completes_with_scorecard(monkeypatch) -> None:
    class FakeAudit:
        def __init__(self, threshold: float):
            self.threshold = threshold

        def analyse(self, candidate, trace_steps, task_value_score):
            from interviu_api.models import TraceAuditSummary

            return TraceAuditSummary(
                status="ok",
                trace_id="trace_test",
                tas_score=88,
                grade="Good",
                passes=True,
                total_steps=len(trace_steps),
                total_tokens=1000,
            )

    monkeypatch.setattr("interviu_api.orchestrator.TraceAuditService", FakeAudit)

    with TestClient(app) as client:
        candidates = client.get("/candidates").json()
        db_health = client.get("/health/database").json()
        candidate_id = candidates[0]["id"]
        run = client.post("/runs", json={"candidate_id": candidate_id}).json()
        scorecard = client.post(f"/runs/{run['id']}/start").json()
        events = client.get(f"/runs/{run['id']}/events").json()
        trace = client.get(f"/runs/{run['id']}/trace").json()
        bundle = client.get(f"/runs/{run['id']}/proof-bundle").json()

    assert scorecard["run_id"] == run["id"]
    assert db_health["backend"] == "sqlite"
    assert scorecard["trace_audit"]["tas_score"] == 88
    assert events
    assert trace["scorecard"]["run_id"] == run["id"]
    assert bundle["schema"] == "interviu.proof_bundle.v1"
    assert bundle["summary"]["event_count"] == len(events)
    assert bundle["database"]["backend"] == "sqlite"
    assert any(probe["id"] == "tracerazor" for probe in bundle["connector_probes"])


def test_connector_probe_reports_local_evidence(monkeypatch) -> None:
    monkeypatch.setattr("interviu_api.connectors._load_tracerazor_client", lambda: object)
    monkeypatch.setattr("interviu_api.connectors.shutil.which", lambda command: f"C:/tools/{command}.exe" if command == "hf" else None)
    monkeypatch.setattr(
        "interviu_api.connectors._run_command",
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
    assert export["schema"] == "interviu.exam_pack.v1"
    assert export["pack"]["id"] == "hr-injection-v1"
    assert len(export["huggingface"]["files"]["data/interviu_exam_rows.jsonl"]) == 6
    assert "README.md" in export["huggingface"]["files"]
    assert imported["id"] == "unit-pack-v1"
    assert imported_export["huggingface"]["files"]["data/interviu_exam_rows.jsonl"][0]["split"] == "seen"
    assert file_export["pack_id"] == "unit-pack-v1"
    assert file_export["row_count"] == 2
    rows_path = Path(file_export["files"]["data/interviu_exam_rows.jsonl"])
    assert rows_path.exists()
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    assert [row["split"] for row in rows] == ["seen", "held_out"]
    assert Path(file_export["files"]["README.md"]).exists()
    assert Path(file_export["files"]["interviu-exam-pack.json"]).exists()
