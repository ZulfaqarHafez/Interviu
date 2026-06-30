"""Per-product Pydantic models, re-exported as one flat namespace.

The models were split out of a single ``models.py`` into per-domain modules so
each product surface owns its own request/response types. This package keeps the
historical ``from assay_api.models import X`` flat import working: every public
model and the shared helpers/aliases are re-exported here.
"""

from __future__ import annotations

from ._common import (
    AdapterType,
    AgentReadiness,
    LessonOutcome,
    RunStatus,
    Seniority,
    SubAgentPriority,
    utc_now,
)
from .candidate import (
    CandidateConfig,
    CandidateResponse,
    TokenCounts,
    ToolCall,
    ToolSpec,
)
from .exam import ExamItem, ExamPack, ExamPackFileExport, ExpectedCheck
from .progress import (
    CandidateProgress,
    CompetencyComparison,
    CompetencyProgress,
    CompetencyTrendPoint,
    DiagnosticLesson,
    RunComparison,
)
from .refinery import (
    AgentResearch,
    AgentResearchSource,
    AgentSpec,
    AgentSpecFileExport,
    SubAgentIdea,
    SubAgentSpec,
)
from .review import ProductReview, ProductReviewer
from .role import (
    BriefCompetency,
    CompetencyRequirement,
    JobScope,
    RequirementSource,
    RoleAnalysis,
    RoleBrief,
)
from .run import RunCreate, RunEvent, RunRecord, Scorecard
from .trace import TraceAuditSummary

__all__ = [
    # shared aliases / helpers
    "AdapterType",
    "AgentReadiness",
    "LessonOutcome",
    "RunStatus",
    "Seniority",
    "SubAgentPriority",
    "utc_now",
    # candidate / agent
    "CandidateConfig",
    "CandidateResponse",
    "TokenCounts",
    "ToolCall",
    "ToolSpec",
    # exam / suites
    "ExamItem",
    "ExamPack",
    "ExamPackFileExport",
    "ExpectedCheck",
    # progress / diagnostics
    "CandidateProgress",
    "CompetencyComparison",
    "CompetencyProgress",
    "CompetencyTrendPoint",
    "DiagnosticLesson",
    "RunComparison",
    # refinery
    "AgentResearch",
    "AgentResearchSource",
    "AgentSpec",
    "AgentSpecFileExport",
    "SubAgentIdea",
    "SubAgentSpec",
    # product review
    "ProductReview",
    "ProductReviewer",
    # role intelligence
    "BriefCompetency",
    "CompetencyRequirement",
    "JobScope",
    "RequirementSource",
    "RoleAnalysis",
    "RoleBrief",
    # runs
    "RunCreate",
    "RunEvent",
    "RunRecord",
    "Scorecard",
    # trace
    "TraceAuditSummary",
]
