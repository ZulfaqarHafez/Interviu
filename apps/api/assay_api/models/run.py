from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..tenancy import current_tenant_id
from ._common import _TENANT_ID_PATTERN, RunStatus, utc_now
from .role import JobScope
from .trace import TraceAuditSummary


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
    tenant_id: str = Field(default_factory=current_tenant_id, pattern=_TENANT_ID_PATTERN)
    candidate_id: str
    exam_pack_id: str = "hr-v1"
    status: RunStatus = "created"
    k: int = 3
    competency_threshold: float = 0.80
    max_transfer_gap: float = 0.20
    tas_threshold: float = 70
    error: str | None = None
    job_scope: JobScope | None = None
    # Set when the run synthesized a tailored exam pack from a role brief; the
    # pack itself lives in the in-process registry and is re-derivable from the
    # persisted ``role_qualified`` event.
    generated_pack_id: str | None = None
    # The originally-requested exam pack, captured before a tailored run overwrites
    # ``exam_pack_id`` with its per-run ``gen-*`` id. Diagnostics/lessons key off
    # this so the closed learning loop carries across reruns even in tailored mode.
    source_pack_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunEvent(BaseModel):
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex[:12]}")
    tenant_id: str = Field(default_factory=current_tenant_id, pattern=_TENANT_ID_PATTERN)
    run_id: str
    sequence: int
    actor: Literal["candidate", "examiner", "grader_panel", "lesson_library", "trace_auditor", "system"]
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    tracerazor_step_id: int | None = None


class Scorecard(BaseModel):
    tenant_id: str = Field(default_factory=current_tenant_id, pattern=_TENANT_ID_PATTERN)
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
    # How the exam/rubric for this run was sourced. ``tailored`` = fully
    # role-researched probes + judge; ``deterministic`` = static pack + keyword
    # grading (offline/no-key); ``partial`` = some stage fell back mid-run.
    qualification_status: Literal["tailored", "deterministic", "partial"] = "deterministic"
    role_brief_summary: str | None = None
    semantic_judge_used: bool = False
    semantic_judge_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
