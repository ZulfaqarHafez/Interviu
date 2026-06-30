from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._common import (
    _MAX_CHECK_TERMS,
    _MAX_CHECK_TEXT_CHARS,
    _MAX_RAW_SCOPE_CHARS,
    _MAX_RUBRIC_CHARS,
    Seniority,
    SubAgentPriority,
    utc_now,
)
from .refinery import AgentResearchSource, SubAgentSpec


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


class BriefCompetency(BaseModel):
    """A competency the candidate agent should be judged on, derived from a deep
    read of the agent's own definition (its ``agent.md``)."""

    key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
    label: str = Field(min_length=1, max_length=_MAX_CHECK_TEXT_CHARS)
    why: str = Field(default="", max_length=_MAX_RUBRIC_CHARS)
    difficulty: Literal["intro", "standard", "adversarial"] = "standard"
    # Keep deterministic keyword grading viable even when the tailored exam is
    # generated: each competency seeds the generated checks with concrete terms.
    seed_keywords: list[str] = Field(default_factory=list, max_length=_MAX_CHECK_TERMS)
    forbidden: list[str] = Field(default_factory=list, max_length=_MAX_CHECK_TERMS)

    model_config = ConfigDict(extra="forbid")


class RoleBrief(BaseModel):
    """What the candidate agent *should* be, researched before judging.

    Produced by the role-qualification stage from the agent's own definition
    (plus optional web research) so the judge is grounded in this specific
    agent/role rather than a fixed static pack. With no OpenAI key it degrades
    to a deterministic brief seeded from role intelligence so the rest of the
    flow keeps working offline.
    """

    schema_: Literal["assay.role_brief.v1"] = Field(default="assay.role_brief.v1", alias="schema")
    run_id: str
    candidate_id: str
    candidate_name: str
    mode: Literal["fast", "deep", "deterministic"]
    status: Literal["ok", "unavailable", "error", "deterministic"]
    model: str | None = None
    role_summary: str = ""
    should_do: list[str] = Field(default_factory=list)
    must_not_do: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    competencies: list[BriefCompetency] = Field(default_factory=list)
    sources: list[AgentResearchSource] = Field(default_factory=list)
    message: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


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
