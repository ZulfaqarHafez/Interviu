from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from interviu_api.main import app


@pytest.fixture(autouse=True)
def _local_sqlite_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests on the isolated sqlite store (see test_api.py)."""

    monkeypatch.setattr("interviu_api.main.load_local_env", lambda: None)
    monkeypatch.delenv("INTERVIU_API_KEYS", raising=False)


def _candidate_id(client: TestClient) -> str:
    return client.get("/candidates").json()[0]["id"]


def test_no_key_configured_allows_open_access() -> None:
    """Auth is opt-in: with no INTERVIU_API_KEYS the API stays open (as today)."""

    with TestClient(app) as client:
        response = client.get("/candidates")
        assert response.status_code == 200


def test_missing_header_rejected_when_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_API_KEYS", "secret-key-1,secret-key-2")
    with TestClient(app) as client:
        response = client.get("/candidates")
        assert response.status_code == 401


def test_wrong_header_rejected_when_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_API_KEYS", "secret-key-1")
    with TestClient(app) as client:
        response = client.get("/candidates", headers={"X-API-Key": "nope"})
        assert response.status_code == 401


def test_correct_header_allows_access_when_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_API_KEYS", "secret-key-1,secret-key-2")
    with TestClient(app) as client:
        response = client.get("/candidates", headers={"X-API-Key": "secret-key-2"})
        assert response.status_code == 200


def test_health_is_exempt_from_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health probes must never require a key, even when auth is configured."""

    monkeypatch.setenv("INTERVIU_API_KEYS", "secret-key-1")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/database").status_code == 200


def test_cors_preflight_allowed_for_default_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/candidates",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_preflight_denied_for_unknown_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/candidates",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette returns 400 for a disallowed preflight origin and never emits
        # the allow-origin header for it.
        assert "access-control-allow-origin" not in response.headers


def test_cors_origins_defaults_to_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    from interviu_api.main import _cors_origins

    monkeypatch.delenv("INTERVIU_CORS_ORIGINS", raising=False)
    assert _cors_origins() == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_cors_origins_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from interviu_api.main import _cors_origins

    monkeypatch.setenv("INTERVIU_CORS_ORIGINS", "https://app.interviu.dev, https://staging.interviu.dev")
    assert _cors_origins() == ["https://app.interviu.dev", "https://staging.interviu.dev"]


def test_rate_limit_enabled_by_default_and_generous(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default rate limiting is active, with limits high enough for local use."""

    from interviu_api import rate_limit as rl

    monkeypatch.delenv("INTERVIU_RATE_LIMIT_ENABLED", raising=False)
    assert rl.rate_limiting_enabled() is True

    with TestClient(app) as client:
        candidate_id = _candidate_id(client)
        for _ in range(5):
            response = client.post("/runs", json={"candidate_id": candidate_id})
            assert response.status_code != 429


def test_rate_limit_enforced_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("INTERVIU_RATE_LIMIT_CREATE_RUN", "2/minute")
    # Reset the in-process limiter storage so prior tests don't bleed counts in.
    from interviu_api import rate_limit as rl

    rl._storage.reset()
    rl._parsed_cache.clear()

    with TestClient(app) as client:
        candidate_id = _candidate_id(client)
        statuses = [
            client.post("/runs", json={"candidate_id": candidate_id}).status_code
            for _ in range(4)
        ]

    assert statuses[0] != 429
    assert statuses[1] != 429
    assert 429 in statuses[2:]


def test_rate_limit_can_be_explicitly_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_RATE_LIMIT_ENABLED", "0")
    from interviu_api import rate_limit as rl

    assert rl.rate_limiting_enabled() is False


def test_hardening_warning_fires_for_insecure_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from interviu_api.main import _check_production_hardening, production_hardening_findings

    warnings: list[str] = []
    monkeypatch.setenv("INTERVIU_ENV", "production")
    monkeypatch.delenv("INTERVIU_API_KEYS", raising=False)
    monkeypatch.delenv("INTERVIU_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("INTERVIU_RATE_LIMIT_ENABLED", "0")
    monkeypatch.delenv("INTERVIU_REQUIRE_HARDENING", raising=False)
    monkeypatch.setattr("interviu_api.main.logger.warning", lambda message: warnings.append(message))

    findings = production_hardening_findings()
    _check_production_hardening()

    assert "INTERVIU_API_KEYS is unset" in findings
    assert "INTERVIU_CORS_ORIGINS is unset" in findings
    assert "INTERVIU_RATE_LIMIT_ENABLED disables rate limiting" in findings
    assert warnings and "Production hardening is incomplete" in warnings[0]


def test_hardening_can_fail_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    from interviu_api.main import _check_production_hardening

    monkeypatch.setenv("INTERVIU_ENV", "production")
    monkeypatch.delenv("INTERVIU_API_KEYS", raising=False)
    monkeypatch.delenv("INTERVIU_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("INTERVIU_REQUIRE_HARDENING", "1")

    with pytest.raises(RuntimeError, match="Production hardening is incomplete"):
        _check_production_hardening()


def test_openai_can_be_disabled_even_when_key_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    from interviu_api.agent_research import resolve_openai_key

    monkeypatch.setenv("INTERVIU_DISABLE_OPENAI", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "real-looking-test-key")

    assert resolve_openai_key() == ""


@pytest.mark.parametrize(
    "endpoint_url",
    [
        "http://127.0.0.1:9000/ask",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/ask",
        "file:///etc/passwd",
    ],
)
def test_create_http_candidate_rejects_ssrf_endpoints(endpoint_url: str) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/candidates",
            json={"name": "Bad HTTP", "adapter_type": "http", "endpoint_url": endpoint_url},
        )

    assert response.status_code == 422


def test_create_http_candidate_accepts_public_resolved_host(monkeypatch: pytest.MonkeyPatch) -> None:
    original = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "candidate.example.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 80))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr("interviu_api.network_guard.socket.getaddrinfo", fake_getaddrinfo)

    with TestClient(app) as client:
        response = client.post(
            "/candidates",
            json={
                "name": "Public HTTP",
                "adapter_type": "http",
                "endpoint_url": "https://candidate.example.com/ask",
            },
        )

    assert response.status_code == 200
    assert response.json()["endpoint_url"] == "https://candidate.example.com/ask"


def test_role_analysis_rejects_bad_override_pack_id() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/role-analysis",
            json={"raw_text": "screen candidates", "override_pack_id": "../bad"},
        )

    assert response.status_code == 422


def test_request_id_header_present_on_responses() -> None:
    with TestClient(app) as client:
        response = client.get("/candidates")
        assert response.headers.get("X-Request-ID")


def test_unexpected_error_returns_safe_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected 500s return a generic {error,request_id} and do not leak str(exc)."""

    secret = "super-secret-internal-detail"

    def _boom() -> list:
        raise RuntimeError(secret)

    with TestClient(app, raise_server_exceptions=False) as client:
        # Patch after startup so the lifespan hook (which also lists candidates)
        # runs cleanly; only the request path raises.
        monkeypatch.setattr("interviu_api.main.list_candidates", _boom)
        response = client.get("/candidates")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "Internal server error"
    assert body["request_id"]
    assert secret not in response.text
