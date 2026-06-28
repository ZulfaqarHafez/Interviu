from __future__ import annotations

import socket

import httpx
import pytest

from assay_api.adapters import CandidateAdapterError, HttpCandidateAdapter, MockCandidateAdapter
from assay_api.models import CandidateConfig


@pytest.fixture(autouse=True)
def _candidate_test_resolves_publicly(monkeypatch: pytest.MonkeyPatch) -> None:
    original = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "candidate.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 80))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr("assay_api.network_guard.socket.getaddrinfo", fake_getaddrinfo)


@pytest.mark.asyncio
async def test_mock_candidate_is_deterministic() -> None:
    config = CandidateConfig(id="cand_test", name="Demo", adapter_type="mock")
    adapter = MockCandidateAdapter(config)

    first = await adapter.ask(context="lesson", question="Should we filter older applicants?")
    second = await adapter.ask(context="lesson", question="Should we filter older applicants?")

    assert first.answer == second.answer
    assert first.tool_calls[0].name == "policy_lookup"
    assert first.tokens.total > 0


@pytest.mark.asyncio
async def test_http_adapter_parses_candidate_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ask"
        return httpx.Response(
            200,
            json={
                "answer": "Use job-related evidence.",
                "reasoning": "Protected traits are irrelevant.",
                "tokens": {"input": 4, "output": 6, "total": 10},
                "tool_calls": [{"name": "lookup", "params": {}, "success": True, "tokens": 3}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)
    response = await adapter.ask(context="ctx", question="q")

    assert response.answer == "Use job-related evidence."
    assert response.tokens.total == 10
    assert response.tool_calls[0].name == "lookup"
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_reports_http_errors() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "bad"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)

    with pytest.raises(CandidateAdapterError):
        await adapter.ask(context="ctx", question="q")
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_rejects_private_endpoint_from_stored_config() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    config = CandidateConfig.model_construct(
        id="cand_legacy",
        name="Legacy HTTP",
        adapter_type="http",
        endpoint_url="http://127.0.0.1:9000/ask",
        metadata={},
    )

    with pytest.raises(CandidateAdapterError, match="public IP"):
        HttpCandidateAdapter(config, client=client)
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_raises_on_timeout() -> None:
    """A timed-out request is surfaced as a CandidateAdapterError, not a leak."""

    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=None)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)

    with pytest.raises(CandidateAdapterError):
        await adapter.ask(context="ctx", question="q")
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_rejects_oversize_response(monkeypatch) -> None:
    monkeypatch.setenv("ASSAY_HTTP_CANDIDATE_MAX_BYTES", "64")
    big_answer = "x" * 4096

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"answer": big_answer, "reasoning": "ok"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)

    with pytest.raises(CandidateAdapterError) as excinfo:
        await adapter.ask(context="ctx", question="q")
    assert "limit" in str(excinfo.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_rejects_non_object_json() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)

    with pytest.raises(CandidateAdapterError):
        await adapter.ask(context="ctx", question="q")
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_rejects_invalid_response_shape() -> None:
    """Malformed tool_calls/tokens are rejected with a CandidateAdapterError."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "answer": "ok",
                "tokens": {"input": "not-a-number"},
                "tool_calls": [{"params": {}}],  # missing required "name"
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)

    with pytest.raises(CandidateAdapterError):
        await adapter.ask(context="ctx", question="q")
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"answer": "x" * 20001, "reasoning": "ok"},
        {"answer": "ok", "reasoning": "x" * 20001},
        {"answer": "ok", "tool_calls": [{"name": f"tool{i}", "params": {}} for i in range(21)]},
        {"answer": "ok", "tool_calls": [{"name": "lookup", "params": {"blob": "x" * 9000}}]},
        {"answer": "ok", "tokens": {"total": -1}},
    ],
)
async def test_http_adapter_rejects_unbounded_candidate_payloads(payload: dict) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://candidate.test")
    config = CandidateConfig(name="HTTP", adapter_type="http", endpoint_url="http://candidate.test/ask")
    adapter = HttpCandidateAdapter(config, client=client)

    with pytest.raises(CandidateAdapterError, match="invalid response shape"):
        await adapter.ask(context="ctx", question="q")
    await client.aclose()
