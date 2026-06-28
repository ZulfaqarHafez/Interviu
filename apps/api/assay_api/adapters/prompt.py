from __future__ import annotations

import asyncio
import os
import random
import re
import time
from typing import Any

from ..agent_research import DEFAULT_FAST_MODEL, resolve_openai_key
from ..models import CandidateConfig, CandidateResponse, TokenCounts
from .base import CandidateAdapter, CandidateAdapterError

_MAX_SYSTEM_PROMPT_CHARS = 20000


class _RateLimited(Exception):
    """Raised internally when the OpenAI key is rate-limited / out of quota so the
    adapter can degrade to a deterministic demo answer instead of failing the run."""


def _retry_after_seconds(exc: Any) -> float | None:
    """Best-effort wait time from a rate-limit error: the ``Retry-After`` header
    if present, else the human hint OpenAI embeds in the message
    (``"try again in 20s"`` / ``"in 1.5s"`` / ``"in 800ms"``)."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            pass
    message = str(getattr(exc, "message", None) or exc)
    match = re.search(r"try again in\s+([\d.]+)\s*(ms|s)", message, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        return value / 1000.0 if match.group(2).lower() == "ms" else value
    return None


class PromptAgentAdapter(CandidateAdapter):
    """Executes a user-supplied agent definition (an ``agent.md`` / ``AGENTS.md``)
    as the candidate under test via OpenAI's ``responses.create``.

    The agent's own markdown drives behaviour: it is sent as the developer/system
    message so the agent's persona, operating principles, and tools take
    precedence over the generic HR-screening preamble Assay adds to every
    ``context``. The endpoint that constructs this adapter only does so in live
    mode (an OpenAI key is present); with no key it falls back to the deterministic
    mock, so this adapter raises if it cannot resolve a key.
    """

    def __init__(self, config: CandidateConfig):
        self.config = config
        system_prompt = (config.system_prompt or "").strip()
        if not system_prompt:
            raise CandidateAdapterError(
                "openai-compatible candidate requires a system_prompt (the agent.md definition)."
            )
        # Defensive size cap before the markdown reaches an LLM call.
        self.system_prompt = system_prompt[:_MAX_SYSTEM_PROMPT_CHARS]
        self.model = config.model or DEFAULT_FAST_MODEL
        # Set true if a call falls back to deterministic answers because the key
        # was rate-limited / out of quota. The orchestrator surfaces this so the
        # verdict is clearly labelled a demo result rather than a live evaluation.
        self.degraded = False
        self.degraded_reason: str | None = None

    async def ask(self, context: str, question: str) -> CandidateResponse:
        # Once this run has been rate-limited, don't keep hammering the dead key on
        # every subsequent probe — answer the rest deterministically right away.
        if self.degraded:
            from .mock import MockCandidateAdapter

            return await MockCandidateAdapter(self.config).ask(context=context, question=question)

        key = resolve_openai_key()
        if not key:
            raise CandidateAdapterError(
                "No OpenAI key found. Add OPENAI_API_KEY (or openai_key) to the project env "
                "file or the API process environment to run the agent in live mode."
            )

        started = time.perf_counter()
        # The agent's own definition is the developer message so its persona wins;
        # the generic Assay preamble arrives only as user-supplied context that
        # the agent should interpret under its own rules.
        user_message = (
            "Assay screening context (treat as task framing, your own agent "
            "definition above takes precedence):\n"
            f"{context}\n\n"
            f"Question:\n{question}"
        )
        try:
            response = await asyncio.to_thread(self._call_openai, key, user_message)
        except _RateLimited as exc:
            # The key is unusable (free-tier 3/min, exhausted quota, etc). Rather
            # than failing the whole run, answer this probe deterministically so
            # the user still reaches a verdict — flagged as a demo result.
            self.degraded = True
            self.degraded_reason = str(exc)
            from .mock import MockCandidateAdapter

            fallback = MockCandidateAdapter(self.config)
            return await fallback.ask(context=context, question=question)

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))

        text = _output_text(response)
        tokens = _token_counts(response, self.system_prompt, context, question, text)
        return CandidateResponse(
            answer=text,
            reasoning="",
            tool_calls=[],
            latency_ms=latency_ms,
            tokens=tokens,
        )

    def _call_openai(self, key: str, user_message: str) -> Any:
        from openai import APIStatusError, OpenAI, RateLimitError

        timeout_s = float(os.environ.get("ASSAY_OPENAI_TIMEOUT_S", "90"))
        client = OpenAI(api_key=key, timeout=timeout_s)
        # A few quick retries absorb a transient 429 on a healthy key. But on a
        # crippled key (free tier ~3/min, where rejected calls themselves keep the
        # window saturated, or an exhausted quota) more retries are futile and just
        # stall the run — so after a short budget we raise _RateLimited and the
        # caller falls back to a deterministic demo answer.
        max_attempts = max(1, int(os.environ.get("ASSAY_OPENAI_MAX_RETRIES", "2")))
        max_wait = float(os.environ.get("ASSAY_OPENAI_MAX_RETRY_WAIT_S", "5"))
        for attempt in range(1, max_attempts + 1):
            try:
                return client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "developer", "content": self.system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                )
            except RateLimitError as exc:
                if attempt >= max_attempts:
                    raise _RateLimited(str(getattr(exc, "message", None) or exc)) from exc
                wait = _retry_after_seconds(exc)
                if wait is None:
                    wait = 2.0 ** attempt
                time.sleep(min(max_wait, wait) + random.uniform(0.2, 0.8))
            except APIStatusError as exc:
                status = getattr(exc, "status_code", None)
                # 429 (quota/limit) -> degrade to demo; transient 5xx -> brief retry.
                if status == 429:
                    raise _RateLimited(str(getattr(exc, "message", None) or exc)) from exc
                if status is not None and 500 <= status < 600 and attempt < max_attempts:
                    time.sleep(min(max_wait, 2.0 ** attempt) + random.uniform(0.2, 0.8))
                    continue
                raise
        # Unreachable: the loop either returns or raises.
        raise CandidateAdapterError("OpenAI request failed after retries.")


def _output_text(response: Any) -> str:
    """Extract reply text robustly across OpenAI SDK response shapes."""

    text = getattr(response, "output_text", None)
    if text:
        return text
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            piece = getattr(content, "text", None)
            if piece:
                chunks.append(piece)
    return "".join(chunks)


def _token_counts(
    response: Any, system_prompt: str, context: str, question: str, answer: str
) -> TokenCounts:
    usage = getattr(response, "usage", None)
    if usage is not None:
        input_tokens = _usage_field(usage, "input_tokens")
        output_tokens = _usage_field(usage, "output_tokens")
        total_tokens = _usage_field(usage, "total_tokens")
        if input_tokens or output_tokens or total_tokens:
            if not total_tokens:
                total_tokens = input_tokens + output_tokens
            return TokenCounts(input=input_tokens, output=output_tokens, total=total_tokens)

    # No usage on the response: estimate ~4 chars per token.
    input_tokens = (len(system_prompt) + len(context) + len(question)) // 4
    output_tokens = len(answer) // 4
    return TokenCounts(
        input=input_tokens,
        output=output_tokens,
        total=input_tokens + output_tokens,
    )


def _usage_field(usage: Any, name: str) -> int:
    value = getattr(usage, name, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(name)
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0
