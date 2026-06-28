from __future__ import annotations

import os
import time
from typing import Any

import httpx
from pydantic import ValidationError

from ..models import CandidateConfig, CandidateResponse, TokenCounts, ToolCall
from ..network_guard import validate_http_candidate_endpoint
from .base import CandidateAdapter, CandidateAdapterError


def _connect_timeout() -> float:
    return float(os.environ.get("ASSAY_HTTP_CANDIDATE_CONNECT_TIMEOUT_S", "10"))


def _read_timeout() -> float:
    return float(os.environ.get("ASSAY_HTTP_CANDIDATE_TIMEOUT_S", "30"))


def _max_response_bytes() -> int:
    return int(os.environ.get("ASSAY_HTTP_CANDIDATE_MAX_BYTES", str(2 * 1024 * 1024)))


def _request_timeout() -> httpx.Timeout:
    read = _read_timeout()
    return httpx.Timeout(read, connect=_connect_timeout())


class HttpCandidateAdapter(CandidateAdapter):
    def __init__(self, config: CandidateConfig, client: httpx.AsyncClient | None = None):
        if config.endpoint_url is None:
            raise CandidateAdapterError("HTTP candidate requires endpoint_url")
        try:
            validate_http_candidate_endpoint(config.endpoint_url)
        except ValueError as exc:
            raise CandidateAdapterError(str(exc)) from exc
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
            # Enforce a connect/read timeout on EVERY request (including a
            # caller-supplied client) so a slow or hung candidate cannot stall a run.
            response = await self._client_for_run().post(
                str(self.config.endpoint_url),
                json=payload,
                timeout=_request_timeout(),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CandidateAdapterError(f"HTTP candidate request failed: {exc}") from exc

        _reject_oversize_response(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise CandidateAdapterError("HTTP candidate returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise CandidateAdapterError("HTTP candidate returned non-object JSON")
        return _parse_candidate_response(data, int((time.perf_counter() - started) * 1000))

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _client_for_run(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_request_timeout())
        return self._client


def _reject_oversize_response(response: httpx.Response) -> None:
    """Reject responses larger than the configured cap before parsing JSON."""

    limit = _max_response_bytes()
    declared = response.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                raise CandidateAdapterError(
                    f"HTTP candidate response exceeds {limit} byte limit"
                )
        except ValueError:
            # Malformed Content-Length: fall through to the body-size check below.
            pass
    # ``response.content`` is already buffered by httpx; guard against servers
    # that omit or understate Content-Length.
    if len(response.content) > limit:
        raise CandidateAdapterError(f"HTTP candidate response exceeds {limit} byte limit")


def _parse_candidate_response(data: dict[str, Any], fallback_latency_ms: int) -> CandidateResponse:
    try:
        tool_calls = [ToolCall.model_validate(item) for item in data.get("tool_calls", [])]
        tokens_payload = data.get("tokens") or {}
        if isinstance(tokens_payload, int):
            tokens = TokenCounts(total=tokens_payload)
        else:
            tokens = TokenCounts.model_validate(tokens_payload)
        if tokens.total == 0:
            tokens.total = tokens.input + tokens.output

        candidate = {
            "answer": str(data.get("answer", "")),
            "reasoning": str(data.get("reasoning", "")),
            "tool_calls": tool_calls,
            "latency_ms": int(data.get("latency_ms") or fallback_latency_ms),
            "tokens": tokens,
        }
        return CandidateResponse.model_validate(candidate)
    except (ValidationError, ValueError, TypeError) as exc:
        raise CandidateAdapterError(
            f"HTTP candidate returned an invalid response shape: {exc}"
        ) from exc
