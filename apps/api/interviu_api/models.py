from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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


class RunCreate(BaseModel):
    candidate_id: str
    exam_pack_id: str = "hr-v1"
    k: int = Field(default=3, ge=1, le=8)
    competency_threshold: float = Field(default=0.80, ge=0, le=1)
    max_transfer_gap: float = Field(default=0.20, ge=0, le=1)
    tas_threshold: float = Field(default=70, ge=0, le=100)


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
