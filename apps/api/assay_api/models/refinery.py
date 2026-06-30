from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ._common import AgentReadiness, SubAgentPriority, utc_now


class SubAgentSpec(BaseModel):
    """A recommended sub-agent the candidate lead agent should delegate to."""

    id: str
    name: str
    role: str
    focus: str
    trigger: str
    sprite: str = "candidate"
    priority: SubAgentPriority = "recommended"
    tools: list[str] = Field(default_factory=list)
    delegation_rule: str
    definition_markdown: str


class SubAgentIdea(BaseModel):
    name: str
    purpose: str


class AgentResearchSource(BaseModel):
    title: str = ""
    url: str


class AgentResearch(BaseModel):
    """OpenAI-backed research on what the candidate agent should be.

    Produced on demand by the Agent Refinery's optional enrichment layer. The
    `fast` mode is a single grounded reasoning call; the `deep` mode uses
    OpenAI web search for cited, externally-grounded recommendations.
    """

    run_id: str
    candidate_id: str
    candidate_name: str
    mode: Literal["fast", "deep"]
    status: Literal["ok", "unavailable", "error"]
    model: str | None = None
    summary: str = ""
    brief_markdown: str = ""
    recommended_tools: list[str] = Field(default_factory=list)
    recommended_subagents: list[SubAgentIdea] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    sources: list[AgentResearchSource] = Field(default_factory=list)
    message: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)


class AgentSpec(BaseModel):
    """Refined, reusable agent definition derived from one interview run.

    The spec is produced deterministically from the run scorecard, retained
    lessons, transfer gap, and the TraceRazor audit. It is an internal
    capability artifact, not a legal or standards compliance claim.
    """

    run_id: str
    candidate_id: str
    candidate_name: str
    exam_pack_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    readiness: AgentReadiness
    headline: str
    agent_markdown: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    tracerazor_actions: list[str] = Field(default_factory=list)
    sub_agents: list[SubAgentSpec] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class AgentSpecFileExport(BaseModel):
    run_id: str
    directory: str
    files: dict[str, str]
    sub_agent_count: int
