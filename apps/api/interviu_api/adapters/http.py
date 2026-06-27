from __future__ import annotations

import time
from typing import Any

import httpx

from ..models import CandidateConfig, CandidateResponse, TokenCounts, ToolCall
from .base import CandidateAdapter, CandidateAdapterError


class HttpCandidateAdapter(CandidateAdapter):
    def __init__(self, config: CandidateConfig, client: httpx.AsyncClient | None = None):
        if config.endpoint_url is None:
            raise CandidateAdapterError("HTTP candidate requires endpoint_url")
        self.config = config
        self._client = client
        self._owns_client = client is None

    async def ask(self, context: str, question: str) -> CandidateResponse:
        started = time.perf_counter()
        payload = {
            "context": context,
            "question": question,
            "candidate_id": self.config.id,
            "metadata": self.config.metadata,
        }
        try:
            response = await self._client_for_run().post(str(self.config.endpoint_url), json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CandidateAdapterError(f"HTTP candidate request failed: {exc}") from exc

        data = response.json()
        if not isinstance(data, dict):
            raise CandidateAdapterError("HTTP candidate returned non-object JSON")
        return _parse_candidate_response(data, int((time.perf_counter() - started) * 1000))

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _client_for_run(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client


def _parse_candidate_response(data: dict[str, Any], fallback_latency_ms: int) -> CandidateResponse:
    tool_calls = [ToolCall.model_validate(item) for item in data.get("tool_calls", [])]
    tokens_payload = data.get("tokens") or {}
    if isinstance(tokens_payload, int):
        tokens = TokenCounts(total=tokens_payload)
    else:
        tokens = TokenCounts.model_validate(tokens_payload)
    if tokens.total == 0:
        tokens.total = tokens.input + tokens.output

    return CandidateResponse(
        answer=str(data.get("answer", "")),
        reasoning=str(data.get("reasoning", "")),
        tool_calls=tool_calls,
        latency_ms=int(data.get("latency_ms") or fallback_latency_ms),
        tokens=tokens,
    )
