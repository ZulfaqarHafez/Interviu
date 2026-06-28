from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .network_guard import validate_http_candidate_endpoint

AgentReadiness = Literal["ready", "refine", "needs_subagents"]
SubAgentPriority = Literal["recommended", "optional"]
Seniority = Literal["intern", "junior", "mid", "senior", "lead", "executive", "unspecified"]

_MAX_RAW_SCOPE_CHARS = 8000
_MAX_CANDIDATE_ANSWER_CHARS = 20000
_MAX_CANDIDATE_REASONING_CHARS = 20000
_MAX_TOOL_CALLS = 20
_MAX_TOOL_PARAM_BYTES = 8192
_MAX_TOOL_TEXT_CHARS = 8000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


AdapterType = Literal["mock", "http", "openai-compatible", "local-command", "mcp-server"]
RunStatus = Literal["created", "running", "completed", "failed"]
LessonOutcome = Literal["pending", "improved", "regressed", "unchanged", "still_failing"]


class ToolCall(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)
    output: str | None = Field(default=None, max_length=_MAX_TOOL_TEXT_CHARS)
    success: bool = True
    error: str | None = Field(default=None, max_length=_MAX_TOOL_TEXT_CHARS)
    tokens: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("params")
    @classmethod
    def _cap_params(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, default=str, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            encoded = str(value).encode("utf-8")
        if len(encoded) > _MAX_TOOL_PARAM_BYTES:
            raise ValueError(f"tool params exceed {_MAX_TOOL_PARAM_BYTES} byte limit")
        return value


class TokenCounts(BaseModel):
    input: int = Field(default=0, ge=0)
    output: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


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

    @field_validator("endpoint_url")
    @classmethod
    def _reject_private_endpoint(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None:
            validate_http_candidate_endpoint(value)
        return value


class CandidateResponse(BaseModel):
    answer: str = Field(max_length=_MAX_CANDIDATE_ANSWER_CHARS)
    reasoning: str = Field(default="", max_length=_MAX_CANDIDATE_REASONING_CHARS)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=_MAX_TOOL_CALLS)
    latency_ms: int = Field(default=0, ge=0)
    tokens: TokenCounts = Field(default_factory=TokenCounts)

    model_config = ConfigDict(extra="forbid")


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

    model_config = ConfigDict(extra="forbid")


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


class ProductReviewer(BaseModel):
    key: str
    name: str
    status: Literal["pass", "warn", "wait"]
    label: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    next_step: str | None = None
    sprite: str = "candidate-audit"


class ProductReview(BaseModel):
    schema_: Literal["interviu.product_review.v1"] = Field(default="interviu.product_review.v1", alias="schema")
    run_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    reviewers: list[ProductReviewer]

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


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
    lessons_applied: list[str] = Field(default_factory=list)
    prior_run_id: str | None = None
    # True when the live OpenAI key was rate-limited / out of quota and the run
    # fell back to deterministic demo answers, so the verdict is illustrative.
    degraded: bool = False
    degraded_reason: str | None = None
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


class DiagnosticLesson(BaseModel):
    """A persistent, per-candidate diagnostic that survives across runs.

    Lessons originate when a candidate fails a competency on a given run; later
    runs of the same candidate on the same exam pack load active lessons and
    re-apply them as context, closing the learning loop. Provenance
    (``origin_run_id``/``origin_score``), application (``applied_run_ids``), and
    outcome (``latest_outcome``) make the diagnostic library a measurable
    learning record rather than a notes file.
    """

    id: str = Field(default_factory=lambda: f"lesson_{uuid4().hex[:10]}")
    candidate_id: str
    exam_pack_id: str
    competency: str
    text: str
    origin_run_id: str
    origin_score: float = 0.0
    origin_variant: Literal["seen", "held_out"] = "held_out"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    applied_run_ids: list[str] = Field(default_factory=list)
    last_applied_at: datetime | None = None
    latest_outcome: LessonOutcome = "pending"
    latest_outcome_score: float | None = None
    active: bool = True


class CompetencyTrendPoint(BaseModel):
    run_id: str
    created_at: datetime
    held_out_score: float
    passed: bool
    transfer_gap: float
    lessons_applied: int = 0


class CompetencyProgress(BaseModel):
    competency: str
    label: str
    points: list[CompetencyTrendPoint] = Field(default_factory=list)
    first_score: float | None = None
    latest_score: float | None = None
    delta: float | None = None
    trend: Literal["improving", "regressing", "flat", "insufficient"] = "insufficient"
    active_lessons: int = 0


class CandidateProgress(BaseModel):
    schema_: Literal["interviu.candidate_progress.v1"] = Field(
        default="interviu.candidate_progress.v1", alias="schema"
    )
    candidate_id: str
    candidate_name: str
    run_count: int = 0
    pass_rate: float = 0.0
    competencies: list[CompetencyProgress] = Field(default_factory=list)
    runs: list[RunRecord] = Field(default_factory=list)
    active_lessons: int = 0
    generated_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CompetencyComparison(BaseModel):
    competency: str
    label: str
    baseline_score: float | None = None
    current_score: float | None = None
    delta: float | None = None
    outcome: Literal["improved", "regressed", "unchanged", "new", "dropped"] = "unchanged"
    baseline_passed: bool | None = None
    current_passed: bool | None = None


class RunComparison(BaseModel):
    schema_: Literal["interviu.run_comparison.v1"] = Field(
        default="interviu.run_comparison.v1", alias="schema"
    )
    run_id: str
    baseline_run_id: str | None = None
    candidate_id: str
    competencies: list[CompetencyComparison] = Field(default_factory=list)
    improved: int = 0
    regressed: int = 0
    unchanged: int = 0
    certified_changed: bool = False
    generated_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
