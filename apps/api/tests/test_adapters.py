from __future__ import annotations

import httpx
import pytest

from interviu_api.adapters import CandidateAdapterError, HttpCandidateAdapter, MockCandidateAdapter
from interviu_api.models import CandidateConfig


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
