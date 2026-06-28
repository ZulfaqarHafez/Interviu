from __future__ import annotations

from assay_api.agent_refinery import _SUBAGENT_TEMPLATES, _slug
from assay_api.models import JobScope
from assay_api.role_intelligence import analyze_job_scope, role_analysis_payload


def _competencies(analysis) -> set[str]:
    return {req.competency for req in analysis.requirements}


def test_screen_and_rank_yields_compliance_and_fairness() -> None:
    analysis = analyze_job_scope(JobScope(raw_text="screen and rank candidates fairly"))

    comps = _competencies(analysis)
    assert "compliance" in comps
    assert "fairness" in comps
    assert analysis.extraction_status == "keyword"

    by_competency = {req.competency: req for req in analysis.requirements}
    for competency in ("compliance", "fairness"):
        req = by_competency[competency]
        assert req.expected_check_ids, f"{competency} should resolve expected_check_ids"
        assert req.covered_by_pack == "hr-v1"
        assert req.rationale, f"{competency} should carry a rationale"


def test_resume_upload_and_pii_pull_in_injection_competencies() -> None:
    analysis = analyze_job_scope(
        JobScope(
            raw_text=(
                "Recruiter screens candidates and reviews each resume upload; an exported "
                "spreadsheet contains ssn fields and must respect gdpr."
            )
        )
    )

    comps = _competencies(analysis)
    assert "prompt_injection_resilience" in comps
    assert "data_minimization" in comps

    # hr-injection-v1 is the pack that tests both, so it must be recommended or supplemental.
    recommended_or_supplemental = {analysis.recommended_exam_pack_id, *analysis.supplemental_pack_ids}
    assert "hr-injection-v1" in recommended_or_supplemental

    # Expected checks resolve from the injection pack items.
    by_competency = {req.competency: req for req in analysis.requirements}
    assert by_competency["prompt_injection_resilience"].expected_check_ids
    assert by_competency["data_minimization"].expected_check_ids


def test_protected_signals_become_flags_never_requirements() -> None:
    analysis = analyze_job_scope(JobScope(raw_text="prefer young energetic digital native"))

    # Protected language is surfaced as flags + notes.
    flags = analysis.job_scope.compliance_flags
    assert any("age" in flag for flag in flags)
    notes_blob = " ".join(analysis.compliance_notes).lower()
    assert "age" in notes_blob

    # The EEOC safeguard: no requirement may cite a protected phrase as its source.
    protected_phrases = ["young", "energetic", "digital native"]
    for req in analysis.requirements:
        for source in req.sources:
            phrase = source.phrase.lower()
            for protected in protected_phrases:
                assert protected not in phrase, (
                    f"Protected phrase '{protected}' leaked into requirement "
                    f"{req.competency} source '{source.phrase}'"
                )

    # Only the always-present floor competencies should exist for protected-only text.
    assert _competencies(analysis) == {"compliance", "fairness"}


def test_recommended_subagent_ids_map_to_templates_or_default() -> None:
    analysis = analyze_job_scope(
        JobScope(
            raw_text=(
                "screen and rank candidates fairly, handle culture fit ambiguity, refuse to "
                "infer sensitive traits, run structured interview panels, parse each resume "
                "upload, call a background-check tool, and protect ssn and gdpr personal data"
            )
        )
    )

    valid_ids = {_slug(key) for key in _SUBAGENT_TEMPLATES} | {_slug("")}
    assert analysis.recommended_subagents, "should recommend at least one sub-agent"
    for sub in analysis.recommended_subagents:
        assert sub.id in valid_ids, f"sub-agent id {sub.id} does not map to a template or default"


def test_floor_competencies_present_for_empty_scope() -> None:
    analysis = analyze_job_scope(JobScope(raw_text=""))

    comps = _competencies(analysis)
    assert "compliance" in comps
    assert "fairness" in comps
    assert analysis.recommended_exam_pack_id == "hr-v1"


def test_payload_is_schema_tagged() -> None:
    payload = role_analysis_payload(JobScope(raw_text="screen and rank candidates"))
    assert payload["schema"] == "assay.role_analysis.v1"
    assert payload["extraction_status"] == "keyword"
    assert len(payload["requirements"]) >= 1
