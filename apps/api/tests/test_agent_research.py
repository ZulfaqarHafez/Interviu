from __future__ import annotations

from fastapi.testclient import TestClient

from assay_api import agent_research
from assay_api.main import app


class _FakeAudit:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def analyse(self, candidate, trace_steps, task_value_score):
        from assay_api.models import TraceAuditSummary

        return TraceAuditSummary(
            status="ok", trace_id="t", tas_score=88, grade="Good", passes=True,
            total_steps=len(trace_steps), total_tokens=1000,
        )


def _started_run(client: TestClient) -> str:
    candidate_id = client.get("/candidates").json()[0]["id"]
    run = client.post("/runs", json={"candidate_id": candidate_id}).json()
    client.post(f"/runs/{run['id']}/start")
    return run["id"]


def test_research_is_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    monkeypatch.setattr(agent_research, "resolve_openai_key", lambda: "")

    with TestClient(app) as client:
        run_id = _started_run(client)
        research = client.post(f"/runs/{run_id}/agent-spec/research?mode=fast").json()

    assert research["status"] == "unavailable"
    assert research["mode"] == "fast"
    assert "OPENAI_API_KEY" in research["message"]


def test_research_fast_returns_structured_result(monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    monkeypatch.setattr(agent_research, "resolve_openai_key", lambda: "test-key")

    def fake_run(key, mode, spec):
        assert key == "test-key"
        assert mode == "fast"
        return {
            "model": "gpt-4.1",
            "summary": "A compliance-first HR screening agent.",
            "brief_markdown": "# Brief\n- be lawful",
            "recommended_tools": ["policy_lookup", "redactor"],
            "recommended_subagents": [{"name": "Privacy Vault Steward", "purpose": "minimize data"}],
            "risks": ["over-trusts tool output"],
            "sources": [],
        }

    monkeypatch.setattr(agent_research, "_run_research", fake_run)

    with TestClient(app) as client:
        run_id = _started_run(client)
        research = client.post(f"/runs/{run_id}/agent-spec/research?mode=fast").json()

    assert research["status"] == "ok"
    assert research["model"] == "gpt-4.1"
    assert research["summary"].startswith("A compliance-first")
    assert "policy_lookup" in research["recommended_tools"]
    assert research["recommended_subagents"][0]["name"] == "Privacy Vault Steward"


def test_research_deep_passes_sources_through(monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    monkeypatch.setattr(agent_research, "resolve_openai_key", lambda: "test-key")

    def fake_run(key, mode, spec):
        assert mode == "deep"
        return {
            "model": "o4-mini-deep-research",
            "summary": "Deep brief.",
            "brief_markdown": "# Deep\nGrounded in sources.",
            "recommended_tools": [],
            "recommended_subagents": [],
            "risks": [],
            "sources": [{"title": "EEOC guidance", "url": "https://example.com/eeoc"}],
        }

    monkeypatch.setattr(agent_research, "_run_research", fake_run)

    with TestClient(app) as client:
        run_id = _started_run(client)
        research = client.post(f"/runs/{run_id}/agent-spec/research?mode=deep").json()

    assert research["status"] == "ok"
    assert research["sources"][0]["url"] == "https://example.com/eeoc"


def test_research_errors_degrade_gracefully(monkeypatch) -> None:
    monkeypatch.setattr("assay_api.orchestrator.TraceAuditService", _FakeAudit)
    monkeypatch.setattr(agent_research, "resolve_openai_key", lambda: "test-key")

    def boom(key, mode, spec):
        raise RuntimeError("openai exploded")

    monkeypatch.setattr(agent_research, "_run_research", boom)

    with TestClient(app) as client:
        run_id = _started_run(client)
        research = client.post(f"/runs/{run_id}/agent-spec/research?mode=fast").json()

    assert research["status"] == "error"
    assert "openai exploded" in research["message"]


def test_research_rejects_invalid_mode() -> None:
    with TestClient(app) as client:
        candidate_id = client.get("/candidates").json()[0]["id"]
        run = client.post("/runs", json={"candidate_id": candidate_id}).json()
        response = client.post(f"/runs/{run['id']}/agent-spec/research?mode=sideways")
        missing = client.post("/runs/run_missing/agent-spec/research?mode=fast")

    assert response.status_code == 422
    assert missing.status_code == 404


def test_env_loader_sets_missing_keys_without_overriding(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / "env"
    env_file.write_text('openai_key="file-secret"\nASSAY_KEEP=from-file\n', encoding="utf-8")

    monkeypatch.delenv("openai_key", raising=False)
    monkeypatch.setenv("ASSAY_KEEP", "from-process")

    agent_research._parse_env_file(env_file)

    assert __import__("os").environ["openai_key"] == "file-secret"
    # Existing process vars win over the file.
    assert __import__("os").environ["ASSAY_KEEP"] == "from-process"


def test_resolve_openai_key_prefers_standard_then_lowercase(monkeypatch) -> None:
    monkeypatch.setattr(agent_research, "load_local_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_KEY", raising=False)
    monkeypatch.setenv("openai_key", "lower-secret")
    assert agent_research.resolve_openai_key() == "lower-secret"

    monkeypatch.setenv("OPENAI_API_KEY", "standard-secret")
    assert agent_research.resolve_openai_key() == "standard-secret"
