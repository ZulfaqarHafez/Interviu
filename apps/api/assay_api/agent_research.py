"""Optional OpenAI-backed research layer for the Agent Refinery.

Given a deterministic :class:`AgentSpec`, this module asks OpenAI "what should
this agent be?" in one of two modes:

* ``fast`` - a single structured reasoning call grounded only in the run's own
  evaluation evidence. Quick and cheap, no web access, no citations.
* ``deep`` - OpenAI deep research with the web-search tool, so the answer is
  grounded in current external best practices and returns cited sources. Slower
  and more expensive; on-demand only.

The whole layer is optional. With no API key it returns a ``status="unavailable"``
result so the rest of Assay keeps working offline. The key is read
server-side only (never exposed to the browser) from a local env file or the
process environment, and an OpenAI call sends the run's candidate answers and
scores to OpenAI, so it is always an explicit, on-demand action.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .agent_refinery import load_agent_spec
from .models import AgentResearch, AgentResearchSource, AgentSpec, SubAgentIdea

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_FAST_MODEL = os.environ.get("ASSAY_OPENAI_MODEL", "gpt-4.1")
DEFAULT_DEEP_MODEL = os.environ.get("ASSAY_OPENAI_DEEP_MODEL", "o4-mini-deep-research")
DISABLE_OPENAI_ENV = "ASSAY_DISABLE_OPENAI"

_RESEARCH_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string", "description": "One or two sentences: what this agent should be."},
        "brief_markdown": {"type": "string", "description": "A markdown brief expanding on the recommendation."},
        "recommended_tools": {"type": "array", "items": {"type": "string"}},
        "recommended_subagents": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"name": {"type": "string"}, "purpose": {"type": "string"}},
                "required": ["name", "purpose"],
            },
        },
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "brief_markdown", "recommended_tools", "recommended_subagents", "risks"],
}

_SYSTEM_PROMPT = (
    "You are an agent architect. Given an evaluation of a candidate HR screening agent, "
    "decide what that agent should be to become reliable and useful: its identity, operating "
    "principles, the tools it needs, the helpers it should delegate to, and the risks to watch. "
    "Ground every recommendation in the supplied evaluation evidence. Be concrete and actionable."
)

_DEEP_SUFFIX = (
    "\n\nUse web search to incorporate current best practices for HR screening agents, agentic "
    "AI design, prompt-injection defense, and fairness/compliance. Cite the sources you rely on. "
    "End your answer with a single fenced ```json block containing keys: summary, brief_markdown, "
    "recommended_tools (array of strings), recommended_subagents (array of {name, purpose}), and "
    "risks (array of strings)."
)


def research_agent_spec(run_id: str, mode: str = "fast") -> AgentResearch | None:
    """Run OpenAI research for a run's agent spec. Returns ``None`` if no spec."""
    if mode not in ("fast", "deep"):
        mode = "fast"
    spec = load_agent_spec(run_id)
    if spec is None:
        return None

    base = {
        "run_id": spec.run_id,
        "candidate_id": spec.candidate_id,
        "candidate_name": spec.candidate_name,
        "mode": mode,
    }

    key = resolve_openai_key()
    if not key:
        return AgentResearch(
            **base,
            status="unavailable",
            message=(
                "No OpenAI key found. Add OPENAI_API_KEY (or openai_key) to the project env file "
                "or the API process environment to enable OpenAI research."
            ),
        )

    try:
        result = _run_research(key, mode, spec)
    except Exception as exc:  # network/SDK/parse failures degrade gracefully.
        return AgentResearch(**base, status="error", message=str(exc))

    return AgentResearch(
        **base,
        status="ok",
        model=result.get("model"),
        summary=result.get("summary", ""),
        brief_markdown=result.get("brief_markdown", ""),
        recommended_tools=list(result.get("recommended_tools", [])),
        recommended_subagents=[
            SubAgentIdea(name=idea.get("name", "Sub-agent"), purpose=idea.get("purpose", ""))
            for idea in result.get("recommended_subagents", [])
            if isinstance(idea, dict)
        ],
        risks=list(result.get("risks", [])),
        sources=[
            AgentResearchSource(title=source.get("title", ""), url=source["url"])
            for source in result.get("sources", [])
            if isinstance(source, dict) and source.get("url")
        ],
    )


def _run_research(key: str, mode: str, spec: AgentSpec) -> dict[str, Any]:
    from openai import OpenAI

    timeout_s = float(os.environ.get("ASSAY_OPENAI_TIMEOUT_S", "300" if mode == "deep" else "90"))
    client = OpenAI(api_key=key, timeout=timeout_s)
    prompt = _build_prompt(spec, mode)

    if mode == "deep":
        model = DEFAULT_DEEP_MODEL
        response = client.responses.create(
            model=model,
            input=[
                {"role": "developer", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt + _DEEP_SUFFIX},
            ],
            tools=[{"type": "web_search_preview"}],
        )
        text = _output_text(response)
        payload = _parse_json_block(text) or {}
        payload.setdefault("brief_markdown", text)
        payload.setdefault("summary", _first_sentence(text))
        payload["sources"] = _extract_sources(response)
        payload["model"] = model
        return payload

    model = DEFAULT_FAST_MODEL
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_schema", "name": "agent_research", "schema": _RESEARCH_JSON_SCHEMA, "strict": True}},
    )
    data = json.loads(_output_text(response))
    data["model"] = model
    data["sources"] = []
    return data


def _build_prompt(spec: AgentSpec, mode: str) -> str:
    sub_agents = "; ".join(f"{sub.name} ({sub.priority}, {sub.focus})" for sub in spec.sub_agents) or "none yet"
    return "\n".join(
        [
            f"Candidate agent: {spec.candidate_name}",
            f"Exam pack: {spec.exam_pack_id}",
            f"Assay readiness verdict: {spec.readiness} - {spec.headline}",
            f"Verified strengths: {', '.join(spec.strengths) or 'none'}",
            f"Gaps to fix: {', '.join(spec.gaps) or 'none'}",
            f"TraceRazor actions: {', '.join(spec.tracerazor_actions) or 'none'}",
            f"Assay's deterministic helper recommendations: {sub_agents}",
            "",
            "Assay's current refined agent definition:",
            spec.agent_markdown,
            "",
            "Task: Recommend what this agent should be. Improve on the deterministic definition above, "
            "keep what the evaluation already verified, and address the gaps and trace findings.",
        ]
    )


def _output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    # Defensive fallback for SDK shapes without the convenience accessor.
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            piece = getattr(content, "text", None)
            if piece:
                chunks.append(piece)
    return "".join(chunks)


def _extract_sources(response: Any) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                url = getattr(annotation, "url", None) or (annotation.get("url") if isinstance(annotation, dict) else None)
                if not url or url in seen:
                    continue
                seen.add(url)
                title = getattr(annotation, "title", None) or (annotation.get("title") if isinstance(annotation, dict) else "")
                sources.append({"title": title or "", "url": url})
    return sources


def _parse_json_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    fence = "```json"
    start = text.find(fence)
    if start != -1:
        rest = text[start + len(fence):]
        end = rest.find("```")
        candidate = rest[:end] if end != -1 else rest
        try:
            return json.loads(candidate.strip())
        except json.JSONDecodeError:
            pass
    # Last resort: try to load the largest {...} span.
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except json.JSONDecodeError:
            return None
    return None


def _first_sentence(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    for end in (". ", "\n"):
        idx = stripped.find(end)
        if idx != -1:
            return stripped[:idx + 1].strip()
    return stripped[:200]


def resolve_openai_key() -> str:
    if os.environ.get(DISABLE_OPENAI_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return ""
    load_local_env()
    for name in ("OPENAI_API_KEY", "OPENAI_KEY", "openai_key"):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return ""


def load_local_env() -> None:
    """Populate os.environ from a local env file for keys that are not already set.

    Looks at ``ASSAY_ENV_FILE`` then ``.env`` then ``env`` at the project root.
    This is dependency-free and never overrides variables already in the
    environment.
    """
    candidates = [os.environ.get("ASSAY_ENV_FILE"), ".env", "env"]
    for name in candidates:
        if not name:
            continue
        path = Path(name)
        if not path.is_absolute():
            path = PROJECT_ROOT / name
        if path.is_file():
            _parse_env_file(path)


def _parse_env_file(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.lower().startswith("export "):
            stripped = stripped[len("export "):]
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
