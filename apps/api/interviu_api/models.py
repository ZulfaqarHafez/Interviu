from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

AgentReadiness = Literal["ready", "refine", "needs_subagents"]
SubAgentPriority = Literal["recommended", "optional"]
Seniority = Literal["intern", "junior", "mid", "senior", "lead", "executive", "unspecified"]

_MAX_RAW_SCOPE_CHARS = 8000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


AdapterType = Literal["mock", "http", "openai-compatible", "local-command", "mcp-server"]
RunStatus = Literal["created", "running", "completed", "failed"]


class ToolCall(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None
    success: bool = True
    error: str | None = None
    tokens: int = 0


class TokenCounts(BaseModel):
    input: int = 0
    output: int = 0
    total: int = 0


class CandidateConfig(BaseModel):
    id: str = Field(default_factory=lambda: f"cand_{uuid4().hex[:10]}")
    name: str
    adapter_type: AdapterType = "mock"
    endpoint_url: HttpUrl | None = None
    model: str | None = None
    system_prompt: str | None = None
    command: list[str] | None = None
    mcp_server_url: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(extra="forbid")


class CandidateResponse(BaseModel):
    answer: str
    reasoning: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    latency_ms: int = 0
    tokens: TokenCounts = Field(default_factory=TokenCounts)


class JobScope(BaseModel):
    """Structured view of a free-text job scope / role description.

    ``raw_text`` is the candidate-supplied free text; the structured fields are
    populated either by the deterministic keyword extractor or by the optional
    OpenAI extraction pass. ``extraction`` records how the structured fields
    were produced.
    """

    raw_text: str = ""
    title: str = ""
    seniority: Seniority = "unspecified"
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    domain: str = ""
    risks: list[str] = Field(default_factory=list)
    compliance_flags: list[str] = Field(default_factory=list)
    extraction: Literal["none", "keyword", "openai-fast", "openai-deep"] = "none"

    model_config = ConfigDict(extra="forbid")

    @field_validator("raw_text")
    @classmethod
    def _cap_raw_text(cls, value: str) -> str:
        # Guard against unbounded input before it reaches the keyword scanner
        # or an LLM call.
        if value and len(value) > _MAX_RAW_SCOPE_CHARS:
            return value[:_MAX_RAW_SCOPE_CHARS]
        return value


class RequirementSource(BaseModel):
    """Traceable evidence linking a job-scope phrase to a competency rule."""

    phrase: str
    field: str
    rule_id: str
    weight: float = 1.0


class CompetencyRequirement(BaseModel):
    """A competency the candidate agent should be evaluated against, derived
    deterministically from the job scope."""

    competency: str
    label: str
    rationale: str
    sources: list[RequirementSource] = Field(default_factory=list)
    expected_check_ids: list[str] = Field(default_factory=list)
    recommended_subagent_id: str | None = None
    priority: SubAgentPriority = "recommended"
    covered_by_pack: str | None = None


class RunCreate(BaseModel):
    candidate_id: str
    exam_pack_id: str = "hr-v1"
    k: int = Field(default=3, ge=1, le=8)
    competency_threshold: float = Field(default=0.80, ge=0, le=1)
    max_transfer_gap: float = Field(default=0.20, ge=0, le=1)
    tas_threshold: float = Field(default=70, ge=0, le=100)
    job_scope: JobScope | None = None


class RunRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:10]}")
    candidate_id: str
    exam_pack_id: str = "hr-v1"
    status: RunStatus = "created"
    k: int = 3
    competency_threshold: float = 0.80
    max_transfer_gap: float = 0.20
    tas_threshold: float = 70
    error: str | None = None
    job_scope: JobScope | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExpectedCheck(BaseModel):
    id: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    weight: float = 1.0


class ExamItem(BaseModel):
    id: str
    competency: str
    prompt: str
    held_out_prompt: str
    rubric: str
    expected_checks: list[ExpectedCheck]
    difficulty: Literal["intro", "standard", "adversarial"] = "standard"
    counterfactual_group: str | None = None


class ExamPack(BaseModel):
    id: str
    name: str
    simulator_model: str
    items: list[ExamItem]


class ExamPackFileExport(BaseModel):
    pack_id: str
    directory: str
    files: dict[str, str]
    row_count: int
    suggested_commands: list[str]


class RunEvent(BaseModel):
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex[:12]}")
    run_id: str
    sequence: int
    actor: Literal["candidate", "examiner", "grader_panel", "lesson_library", "trace_auditor", "system"]
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    tracerazor_step_id: int | None = None


class TraceAuditSummary(BaseModel):
    status: Literal["ok", "insufficient_steps", "unavailable", "error"]
    trace_id: str | None = None
    tas_score: float | None = None
    grade: str | None = None
    passes: bool = False
    total_steps: int = 0
    total_tokens: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    savings: dict[str, Any] = Field(default_factory=dict)
    fixes: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class Scorecard(BaseModel):
    run_id: str
    status: RunStatus = "completed"
    certified: bool
    certificate_label: str = "Internal capability bar only"
    k: int
    thresholds: dict[str, float]
    simulator_model: str
    pass_at_k: dict[str, bool]
    competency_scores: dict[str, float]
    seen_scores: dict[str, float]
    held_out_scores: dict[str, float]
    transfer_gap: dict[str, float]
    grader_disagreement: float
    trace_audit: TraceAuditSummary
    failure_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


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


class RoleAnalysis(BaseModel):
    """Deterministic-first mapping from a job scope to the competencies,
    expected checks, and sub-agents the candidate agent should be evaluated
    against. Produced by the role-intelligence layer.
    """

    job_scope: JobScope
    recommended_exam_pack_id: str
    supplemental_pack_ids: list[str] = Field(default_factory=list)
    requirements: list[CompetencyRequirement] = Field(default_factory=list)
    recommended_subagents: list[SubAgentSpec] = Field(default_factory=list)
    uncovered_competencies: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
    extraction_status: Literal["keyword", "openai-fast", "openai-deep", "unavailable", "error"] = "keyword"
    sources: list[AgentResearchSource] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
