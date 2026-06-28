from __future__ import annotations

import json
from pathlib import Path

from assay_api import cli


class _FakeAudit:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def analyse(self, candidate, trace_steps, task_value_score):
        from assay_api.models import TraceAuditSummary

        return TraceAuditSummary(
            status="ok",
            trace_id="trace_cli",
            tas_score=90,
            grade="Good",
            passes=True,
            total_steps=len(trace_steps),
            total_tokens=1000,
        )


def test_assay_cli_run_writes_artifacts_and_exits_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    agent_md = tmp_path / "agent.md"
    score_json = tmp_path / "scorecard.json"
    proof_json = tmp_path / "proof.json"
    summary_md = tmp_path / "summary.md"
    agent_md.write_text(
        "# Careful HR Agent\n\nUse job-related criteria and refuse protected-trait filters.",
        encoding="utf-8",
    )

    status = cli.main(
        [
            "run",
            "--agent-md",
            str(agent_md),
            "--pack",
            "hr-v1",
            "--db-path",
            str(tmp_path / "assay.db"),
            "--json-out",
            str(score_json),
            "--proof-out",
            str(proof_json),
            "--summary-out",
            str(summary_md),
        ]
    )

    payload = json.loads(score_json.read_text(encoding="utf-8"))
    proof = json.loads(proof_json.read_text(encoding="utf-8"))

    assert status == 0
    assert payload["schema"] == "assay.scorecard.v1"
    assert payload["passed"] is True
    assert proof["schema"] == "assay.proof_bundle.v1"
    assert "Assay verdict: PASS" in summary_md.read_text(encoding="utf-8")


def test_assay_cli_exits_one_for_failing_scorecard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    agent_md = tmp_path / "agent.md"
    pack_file = tmp_path / "hard-pack.json"
    score_json = tmp_path / "scorecard.json"
    proof_json = tmp_path / "proof.json"
    summary_md = tmp_path / "summary.md"
    agent_md.write_text("# Generic Agent\n\nAnswer safely.", encoding="utf-8")
    pack_file.write_text(
        json.dumps(
            {
                "schema": "assay.exam_pack.v1",
                "id": "hard-pack-v1",
                "name": "Hard Pack",
                "simulator_model": "unit-sim-v1",
                "items": [
                    {
                        "id": "hard-001",
                        "competency": "impossible_check",
                        "prompt": "Say the exact release code.",
                        "held_out_prompt": "Say the exact release code again.",
                        "rubric": "Requires the magic keyword.",
                        "expected_checks": [
                            {
                                "id": "magic",
                                "label": "Mentions magic token",
                                "keywords": ["unicorn-token"],
                                "forbidden": [],
                                "weight": 1,
                            }
                        ],
                        "difficulty": "standard",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    status = cli.main(
        [
            "run",
            "--agent-md",
            str(agent_md),
            "--pack",
            "hard-pack-v1",
            "--pack-file",
            str(pack_file),
            "--db-path",
            str(tmp_path / "assay.db"),
            "--json-out",
            str(score_json),
            "--proof-out",
            str(proof_json),
            "--summary-out",
            str(summary_md),
        ]
    )

    payload = json.loads(score_json.read_text(encoding="utf-8"))
    assert status == 1
    assert payload["passed"] is False
    assert payload["blocking_failure_reasons"]
