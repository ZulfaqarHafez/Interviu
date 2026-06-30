from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..tenancy import current_tenant_id
from ._common import _TENANT_ID_PATTERN, LessonOutcome, utc_now
from .run import RunRecord


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
    tenant_id: str = Field(default_factory=current_tenant_id, pattern=_TENANT_ID_PATTERN)
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
    schema_: Literal["assay.candidate_progress.v1"] = Field(
        default="assay.candidate_progress.v1", alias="schema"
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
    schema_: Literal["assay.run_comparison.v1"] = Field(
        default="assay.run_comparison.v1", alias="schema"
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
