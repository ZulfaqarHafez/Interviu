"""Role intelligence: turn a free-text job scope into the competencies, checks,
and sub-agents the candidate agent should be evaluated against.

The mapper is deterministic-first. A keyword pass (no network, no LLM) maps
job-scope signal phrases onto the competencies already covered by the registered
exam packs, resolves the concrete ``expected_checks`` each competency is tested
by, and reuses the Agent Refinery's sub-agent templates so recommendations stay
traceable and never duplicate template logic.

An optional OpenAI extraction pass (:func:`extract_job_scope_openai`) only
improves recall: it parses the free text into structured job fields and flags
protected-attribute language separately. The deterministic mapper still runs
afterwards, so the decision is always explainable.

A hard EEOC safeguard runs on every analysis: protected-attribute signals
(age, national origin, family status, disability, religion) are recorded as
compliance flags/notes and NEVER turned into a competency requirement.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .agent_refinery import _cap_sub_agents, _labelize, _slug, _specialist
from .exam_packs import EXAM_PACKS, get_exam_pack
from .models import (
    CompetencyRequirement,
    JobScope,
    RequirementSource,
    RoleAnalysis,
    Seniority,
    SubAgentSpec,
)

# Each rule maps job-scope signal phrases to an existing pack competency.
# ``keywords`` are matched case-insensitively against the lowercased scope text;
# ``pack`` is the exam pack that tests this competency.
_COMPETENCY_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "r-compliance",
        "competency": "compliance",
        "pack": "hr-v1",
        "keywords": [
            "screen", "rank candidates", "shortlist", "employment law", "eeo",
            "equal opportunity", "compliance", "hiring decision",
        ],
    },
    {
        "rule_id": "r-fairness",
        "competency": "fairness",
        "pack": "hr-v1",
        "keywords": ["fair", "bias", "diversity", "inclusion", "consistent", "objective", "scorecard"],
    },
    {
        "rule_id": "r-ambiguity",
        "competency": "ambiguity_handling",
        "pack": "hr-v1",
        "keywords": ["culture fit", "stakeholder", "ambiguous", "vague", "judgment", "subjective"],
    },
    {
        "rule_id": "r-refusal",
        "competency": "refusal_boundaries",
        "pack": "hr-v1",
        "keywords": [
            "sensitive", "background check", "private", "infer", "social media",
            "health", "pregnan", "religio",
        ],
    },
    {
        "rule_id": "r-ethics",
        "competency": "interview_ethics",
        "pack": "hr-v1",
        "keywords": ["interview", "ask questions", "structured interview", "panel", "phone screen"],
    },
    {
        "rule_id": "r-injection",
        "competency": "prompt_injection_resilience",
        "pack": "hr-injection-v1",
        "keywords": [
            "resume", "portfolio", "attachment", "upload", "parse documents", "ats", "untrusted",
        ],
    },
    {
        "rule_id": "r-tool",
        "competency": "tool_output_hygiene",
        "pack": "hr-injection-v1",
        "keywords": [
            "tool", "integration", "api", "vendor", "background-check tool", "reference check",
        ],
    },
    {
        "rule_id": "r-pii",
        "competency": "data_minimization",
        "pack": "hr-injection-v1",
        "keywords": ["ssn", "pii", "medical", "spreadsheet", "personal data", "gdpr", "data minimization"],
    },
]

# Protected-attribute signals. A hit is recorded as a compliance flag/note only;
# it NEVER becomes a competency requirement.
_PROTECTED_SIGNALS: dict[str, list[str]] = {
    "age": ["age", "young", "energetic", "digital native"],
    "national_origin": ["native speaker", "accent", "local candidate"],
    "family_status": ["childcare", "parental", "maternity", "family plans", "pregnant", "pregnancy"],
    "disability": ["able-bodied", "no accommodation"],
    "religion": ["religion", "religious", "faith"],
    "sex": ["gender", "sexual orientation"],
    "race": ["race", "ethnicity", "ethnic"],
}

_SENIORITY_RULES: dict[str, list[str]] = {
    "senior": ["senior", "lead", "principal", "staff", "head of", "manager"],
    "junior": ["junior", "entry", "associate", "intern", "graduate"],
}

# Floor competencies that are always evaluated, even when no rule keyword hits.
_FLOOR_COMPETENCIES: list[tuple[str, str]] = [
    ("compliance", "hr-v1"),
    ("fairness", "hr-v1"),
]
_FLOOR_RULE_ID = "r-floor"

_DEFAULT_PACK_ID = "hr-v1"


def _scope_text(job_scope: JobScope) -> str:
    """Lowercased haystack combining raw text and structured fields."""
    parts: list[str] = [job_scope.raw_text, job_scope.title, job_scope.domain]
    for collection in (
        job_scope.responsibilities,
        job_scope.required_skills,
        job_scope.nice_to_have,
        job_scope.qualifications,
        job_scope.risks,
    ):
        parts.extend(collection)
    return "\n".join(part for part in parts if part).lower()


def _sentence_for(text: str, keyword: str) -> str:
    """Return the sentence (or short window) containing ``keyword``.

    Falls back to the keyword itself when no sentence boundary is found. The
    phrase makes a RequirementSource human-readable evidence trail.
    """
    idx = text.find(keyword)
    if idx == -1:
        return keyword
    # Find sentence boundaries around the match.
    start = max(
        text.rfind(".", 0, idx),
        text.rfind("\n", 0, idx),
        text.rfind(";", 0, idx),
    )
    start = 0 if start == -1 else start + 1
    end_candidates = [pos for pos in (text.find(".", idx), text.find("\n", idx), text.find(";", idx)) if pos != -1]
    end = min(end_candidates) if end_candidates else len(text)
    sentence = text[start:end].strip()
    return sentence or keyword


def _detect_seniority(text: str) -> Seniority:
    for keyword in _SENIORITY_RULES["senior"]:
        if keyword in text:
            return "senior"
    for keyword in _SENIORITY_RULES["junior"]:
        if keyword in text:
            return "junior"
    return "unspecified"


def _expected_check_ids(competency: str, pack_id: str) -> tuple[list[str], str | None]:
    """Return (expected_check_ids, covered_by_pack) for a competency.

    Searches the named pack first, then any registered pack, so a competency is
    reported as covered if *some* pack tests it. Returns an empty list and
    ``None`` when no registered pack tests the competency.
    """
    pack_ids = [pack_id] + [pid for pid in EXAM_PACKS if pid != pack_id]
    for pid in pack_ids:
        try:
            pack = get_exam_pack(pid)
        except KeyError:
            continue
        for item in pack.items:
            if item.competency == competency:
                return [check.id for check in item.expected_checks], pid
    return [], None


def _contains_protected(text: str) -> dict[str, list[str]]:
    """Return mapping of protected category -> matched phrases present in text."""
    hits: dict[str, list[str]] = {}
    for category, phrases in _PROTECTED_SIGNALS.items():
        matched = [phrase for phrase in phrases if phrase in text]
        if matched:
            hits[category] = matched
    return hits


def analyze_job_scope(job_scope: JobScope, override_pack_id: str | None = None) -> RoleAnalysis:
    """Map a job scope to competency requirements, packs, and sub-agents.

    Deterministic. Reuses the registered exam packs for expected checks and the
    Agent Refinery's sub-agent templates for recommendations. Protected-attribute
    language is recorded as compliance flags/notes only, never as a requirement.
    """
    text = _scope_text(job_scope)
    seniority = job_scope.seniority
    if seniority == "unspecified":
        seniority = _detect_seniority(text)

    # 1) Match competency rules. Floor competencies are always present.
    requirements: dict[str, CompetencyRequirement] = {}
    # competency -> the pack that should test it (for sub-agent rubric lookup).
    competency_pack: dict[str, str] = {}
    # pack_id -> count of competencies it contributes.
    pack_votes: dict[str, int] = {}

    def _ensure_requirement(competency: str, pack_id: str) -> CompetencyRequirement:
        if competency not in requirements:
            check_ids, covered_by = _expected_check_ids(competency, pack_id)
            requirements[competency] = CompetencyRequirement(
                competency=competency,
                label=_labelize(competency),
                rationale="",
                sources=[],
                expected_check_ids=check_ids,
                recommended_subagent_id=_slug(competency),
                priority="recommended",
                covered_by_pack=covered_by,
            )
            competency_pack[competency] = covered_by or pack_id
            if covered_by:
                pack_votes[covered_by] = pack_votes.get(covered_by, 0) + 1
        return requirements[competency]

    # Floor competencies first so they always appear, with a deterministic source.
    for competency, pack_id in _FLOOR_COMPETENCIES:
        req = _ensure_requirement(competency, pack_id)
        req.sources.append(
            RequirementSource(
                phrase="floor competency (always evaluated)",
                field="floor",
                rule_id=_FLOOR_RULE_ID,
                weight=1.0,
            )
        )

    # Keyword rules.
    for rule in _COMPETENCY_RULES:
        matched_phrases: list[str] = []
        for keyword in rule["keywords"]:
            if keyword in text:
                matched_phrases.append(keyword)
        if not matched_phrases:
            continue
        req = _ensure_requirement(rule["competency"], rule["pack"])
        for keyword in matched_phrases:
            req.sources.append(
                RequirementSource(
                    phrase=_sentence_for(text, keyword) or keyword,
                    field="raw_text",
                    rule_id=rule["rule_id"],
                    weight=1.0,
                )
            )

    # 2) Rationale + uncovered tracking.
    uncovered: list[str] = []
    for competency, req in requirements.items():
        signal_phrases = [src.phrase for src in req.sources if src.rule_id != _FLOOR_RULE_ID]
        if signal_phrases:
            req.rationale = (
                f"Job scope signals {req.label.lower()} (e.g. \"{signal_phrases[0]}\")."
            )
        else:
            req.rationale = (
                f"{req.label} is a baseline screening competency every HR agent is held to."
            )
        if not req.expected_check_ids or req.covered_by_pack is None:
            uncovered.append(competency)

    # 3) Pick recommended pack: most matched competencies, default hr-v1.
    #    Ties break toward the default pack, then registration order.
    pack_order = list(EXAM_PACKS)

    def _pack_rank(pid: str) -> tuple[int, int, int]:
        registered = pack_order.index(pid) if pid in pack_order else len(pack_order)
        return (pack_votes[pid], 1 if pid == _DEFAULT_PACK_ID else 0, -registered)

    if override_pack_id:
        recommended_pack_id = override_pack_id
    elif pack_votes:
        recommended_pack_id = max(pack_votes, key=_pack_rank)
    else:
        recommended_pack_id = _DEFAULT_PACK_ID

    supplemental = sorted(pid for pid in pack_votes if pid != recommended_pack_id)

    # 4) Sub-agents: one specialist per matched competency, reusing the refinery.
    sub_agents: list[SubAgentSpec] = []
    for competency, req in requirements.items():
        pack_id = competency_pack.get(competency, recommended_pack_id)
        try:
            pack = get_exam_pack(pack_id)
        except KeyError:
            pack = get_exam_pack(recommended_pack_id)
        spec = _specialist(
            competency=competency,
            pack=pack,
            held_score=None,
            priority=req.priority,
            trigger=req.rationale,
        )
        sub_agents.append(spec)
    sub_agents = _cap_sub_agents(sub_agents)
    recommended_subagent_ids = {agent.id for agent in sub_agents}
    # Keep requirement -> sub-agent links honest after capping.
    for req in requirements.values():
        if req.recommended_subagent_id not in recommended_subagent_ids:
            req.recommended_subagent_id = None

    # 5) PROTECTED PASS (EEOC safeguard): flag protected language, never a requirement.
    compliance_flags = list(job_scope.compliance_flags)
    compliance_notes: list[str] = []
    for category, matched in _contains_protected(text).items():
        label = _labelize(category)
        flag = f"protected:{category}"
        if flag not in compliance_flags:
            compliance_flags.append(flag)
        phrases = ", ".join(f'"{phrase}"' for phrase in matched)
        compliance_notes.append(
            f"Protected attribute language detected ({label}): {phrases}. "
            "This is recorded as a compliance flag only and is never used as a screening requirement."
        )
    scoped = job_scope.model_copy(update={"seniority": seniority, "compliance_flags": compliance_flags})

    return RoleAnalysis(
        job_scope=scoped,
        recommended_exam_pack_id=recommended_pack_id,
        supplemental_pack_ids=supplemental,
        requirements=list(requirements.values()),
        recommended_subagents=sub_agents,
        uncovered_competencies=uncovered,
        compliance_notes=compliance_notes,
        extraction_status="keyword",
        sources=[],
    )


# ---------------------------------------------------------------------------
# Optional OpenAI extraction (recall improver only).
# ---------------------------------------------------------------------------

_JOB_SCOPE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "seniority": {
            "type": "string",
            "enum": ["intern", "junior", "mid", "senior", "lead", "executive", "unspecified"],
        },
        "responsibilities": {"type": "array", "items": {"type": "string"}},
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "nice_to_have": {"type": "array", "items": {"type": "string"}},
        "qualifications": {"type": "array", "items": {"type": "string"}},
        "domain": {"type": "string"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "compliance_flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title", "seniority", "responsibilities", "required_skills", "nice_to_have",
        "qualifications", "domain", "risks", "compliance_flags",
    ],
}

_EXTRACT_SYSTEM_PROMPT = (
    "You extract structured job requirements from a free-text job scope for an HR "
    "screening agent. Extract job-related requirements only (responsibilities, skills, "
    "qualifications, domain, operational risks). Flag any protected-attribute language "
    "(age, national origin, family/parental status, disability, religion, sex, race) "
    "separately in compliance_flags using the form 'protected:<category>'. NEVER list a "
    "protected trait or protected-attribute preference as a responsibility, skill, or "
    "qualification."
)


def extract_job_scope_openai(raw_text: str, mode: str = "fast") -> JobScope | None:
    """Extract structured job fields from free text using OpenAI.

    Returns ``None`` when no OpenAI key is configured so the caller can fall back
    to a keyword-only :class:`JobScope`. The deterministic mapper still runs after
    extraction, so the LLM only improves recall.
    """
    from .agent_research import resolve_openai_key

    if mode not in ("fast", "deep"):
        mode = "fast"
    raw_text = (raw_text or "")[:8000]

    key = resolve_openai_key()
    if not key:
        return None

    data = _run_extraction(key, raw_text, mode)
    extraction = "openai-deep" if mode == "deep" else "openai-fast"
    return JobScope(
        raw_text=raw_text,
        title=str(data.get("title", "")),
        seniority=data.get("seniority", "unspecified") or "unspecified",
        responsibilities=[str(x) for x in data.get("responsibilities", [])],
        required_skills=[str(x) for x in data.get("required_skills", [])],
        nice_to_have=[str(x) for x in data.get("nice_to_have", [])],
        qualifications=[str(x) for x in data.get("qualifications", [])],
        domain=str(data.get("domain", "")),
        risks=[str(x) for x in data.get("risks", [])],
        compliance_flags=[str(x) for x in data.get("compliance_flags", [])],
        extraction=extraction,  # type: ignore[arg-type]
    )


def _run_extraction(key: str, raw_text: str, mode: str) -> dict[str, Any]:
    from openai import OpenAI

    from .agent_research import DEFAULT_FAST_MODEL

    timeout_s = float(os.environ.get("ASSAY_OPENAI_TIMEOUT_S", "90"))
    client = OpenAI(api_key=key, timeout=timeout_s)
    model = DEFAULT_FAST_MODEL
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Job scope:\n{raw_text}"},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "job_scope",
                "schema": _JOB_SCOPE_JSON_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(_extraction_text(response))


def _extraction_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            piece = getattr(content, "text", None)
            if piece:
                chunks.append(piece)
    return "".join(chunks) or "{}"


# ---------------------------------------------------------------------------
# Payload helpers (mirror agent_spec_payload).
# ---------------------------------------------------------------------------


def role_analysis_payload(job_scope: JobScope, override_pack_id: str | None = None) -> dict[str, Any]:
    """Return the schema-tagged JSON payload for a role analysis."""
    analysis = analyze_job_scope(job_scope, override_pack_id=override_pack_id)
    return {"schema": "assay.role_analysis.v1", **analysis.model_dump(mode="json")}


def role_analysis_for_run(run_id: str) -> dict[str, Any] | None:
    """Return the role-analysis payload for a persisted run, or ``None``.

    Uses the run's stored job scope (or an empty scope) and treats the run's
    exam pack as a pack override so the analysis reflects the run's actual pack.
    """
    from .database import get_run

    run = get_run(run_id)
    if run is None:
        return None
    job_scope = run.job_scope or JobScope()
    return role_analysis_payload(job_scope, override_pack_id=run.exam_pack_id)
