from __future__ import annotations

from assay_api.agent_refinery import build_agent_spec
from assay_api.exam_packs import get_exam_pack
from assay_api.models import (
    CandidateConfig,
    RunEvent,
    RunRecord,
    Scorecard,
    TraceAuditSummary,
)


def _scorecard(
    run_id: str,
    *,
    held: dict[str, float],
    transfer_gap: dict[str, float],
    pass_at_k: dict[str, bool],
    certified: bool,
    audit: TraceAuditSummary,
    failures: list[str] | None = None,
) -> Scorecard:
    return Scorecard(
        run_id=run_id,
        certified=certified,
        k=3,
        thresholds={"competency": 0.8, "max_transfer_gap": 0.2, "tas": 70},
        simulator_model="assay-deterministic-sim-v1",
        pass_at_k=pass_at_k,
        competency_scores=held,
        seen_scores=held,
        held_out_scores=held,
        transfer_gap=transfer_gap,
        grader_disagreement=0.04,
        trace_audit=audit,
        failure_reasons=failures or [],
    )


def _ok_audit(passes: bool = True, tas: float = 88.0, fixes=None) -> TraceAuditSummary:
    return TraceAuditSummary(
        status="ok",
        trace_id="trace_test",
        tas_score=tas,
        grade="Good",
        passes=passes,
        total_steps=8,
        total_tokens=1200,
        savings={"tokens_saved": 40, "reduction_pct": 12.0},
        fixes=fixes or [],
    )


def test_certified_run_is_ready_and_recommends_no_required_subagents() -> None:
    run = RunRecord(id="run_ready", candidate_id="cand_x", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_x", name="Solid Agent", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    scorecard = _scorecard(
        run.id,
        held={"compliance": 0.95, "fairness": 0.9},
        transfer_gap={"compliance": 0.0, "fairness": 0.05},
        pass_at_k={"compliance": True, "fairness": True},
        certified=True,
        audit=_ok_audit(),
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, [])

    assert spec.readiness == "ready"
    assert spec.strengths  # at least one verified competency
    assert spec.gaps == []
    assert "# Solid Agent - Operating Notes" in spec.agent_markdown
    assert "## Guardrails" in spec.agent_markdown
    assert "READY" in spec.agent_markdown
    # No competency failed, so no specialist helper is marked recommended.
    assert all(agent.priority == "optional" for agent in spec.sub_agents)
    assert spec.metrics["recommended_subagents"] == 0


def test_failing_competency_recommends_specialist_subagent() -> None:
    run = RunRecord(id="run_gap", candidate_id="cand_y", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_y", name="Weak Agent", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    scorecard = _scorecard(
        run.id,
        held={"compliance": 0.95, "fairness": 0.5},
        transfer_gap={"compliance": 0.0, "fairness": 0.35},
        pass_at_k={"compliance": True, "fairness": False},
        certified=False,
        audit=_ok_audit(),
        failures=["fairness failed pass^3 on held-out variants"],
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, [])

    assert spec.readiness == "needs_subagents"
    recommended = [agent for agent in spec.sub_agents if agent.priority == "recommended"]
    assert any("fairness" in agent.id for agent in recommended)
    # The over-threshold transfer gap recruits a held-out verifier too.
    assert any(agent.id == "heldout-verifier" for agent in recommended)
    assert any("Fairness" in line for line in spec.gaps)
    assert "Must-fix rules" in spec.agent_markdown


def test_trace_audit_failure_recommends_trace_auditor() -> None:
    run = RunRecord(id="run_trace", candidate_id="cand_z", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_z", name="Chatty Agent", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    scorecard = _scorecard(
        run.id,
        held={"compliance": 0.95},
        transfer_gap={"compliance": 0.0},
        pass_at_k={"compliance": True},
        certified=False,
        audit=_ok_audit(passes=False, tas=42.0),
        failures=["TraceRazor TAS 42.0 is below 70.0"],
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, [])

    trace_agents = [agent for agent in spec.sub_agents if agent.id == "trace-auditor"]
    assert trace_agents and trace_agents[0].priority == "recommended"
    assert "tracerazor.Tracer" in trace_agents[0].tools
    assert any("TraceRazor" in action for action in spec.tracerazor_actions)


def test_certified_run_with_trace_fixes_keeps_subagents_optional() -> None:
    run = RunRecord(id="run_fixes", candidate_id="cand_f", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_f", name="Tidy Agent", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    scorecard = _scorecard(
        run.id,
        held={"compliance": 0.95},
        transfer_gap={"compliance": 0.0},
        pass_at_k={"compliance": True},
        certified=True,
        audit=_ok_audit(fixes=[{"fix_type": "trim", "target": "step-2", "estimated_token_savings": 30}]),
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, [])

    # Certified runs must never carry a "recommended" helper, even with fixes.
    assert spec.readiness == "ready"
    assert all(agent.priority == "optional" for agent in spec.sub_agents)
    assert spec.metrics["recommended_subagents"] == 0
    assert "recommended helper" not in spec.headline


def test_subagent_cap_reserves_cross_cutting_auditors() -> None:
    run = RunRecord(id="run_cap", candidate_id="cand_c", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_c", name="Overloaded Agent", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    held = {f"comp_{index}": 0.4 for index in range(7)}
    scorecard = _scorecard(
        run.id,
        held=held,
        transfer_gap={"comp_0": 0.5, **{f"comp_{index}": 0.0 for index in range(1, 7)}},
        pass_at_k={key: False for key in held},
        certified=False,
        audit=TraceAuditSummary(status="unavailable", passes=False),
        failures=["many competencies failed"],
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, [])

    ids = {agent.id for agent in spec.sub_agents}
    assert len(spec.sub_agents) == 6  # _MAX_SUBAGENTS
    # The high-signal cross-cutting auditors survive the cap.
    assert "trace-auditor" in ids
    assert "heldout-verifier" in ids


def test_empty_held_scores_is_not_self_contradictory() -> None:
    run = RunRecord(id="run_empty", candidate_id="cand_e", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_e", name="Unscored Agent", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    scorecard = _scorecard(
        run.id,
        held={},
        transfer_gap={},
        pass_at_k={},
        certified=False,
        audit=TraceAuditSummary(status="unavailable", passes=False),
        failures=["TraceRazor audit status is unavailable"],
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, [])

    assert spec.readiness == "refine"
    assert "No competencies were scored for this run." in spec.agent_markdown
    assert "every competency met its threshold" not in spec.agent_markdown


_VALID_SPRITES = {
    "candidate", "candidate-thinking", "candidate-pass", "candidate-fail", "domain", "edge",
    "judge", "simulator", "tracerazor", "supabase", "hugging-face", "vercel", "injection-scroll",
    "tool-trap", "privacy-vault", "dataset-crate", "mcp-plug", "model-chip", "http-antenna",
    "local-command", "audit-shard", "candidate-walk-left", "candidate-walk-right", "candidate-shield",
    "candidate-document", "candidate-audit", "candidate-celebrate", "candidate-tired",
    "candidate-terminal", "candidate-lock", "candidate-ready", "candidate-question",
    "candidate-evidence", "candidate-review", "candidate-approved", "candidate-alert",
    "candidate-export", "candidate-proof", "candidate-calm",
}


def test_all_emitted_subagent_sprites_exist_in_sprite_sheet() -> None:
    # Force every template + cross-cutting auditor to fire across both packs so a
    # typo'd sprite name would render a blank tile in the UI and fail here instead.
    candidate = CandidateConfig(id="cand_s", name="Sprite Agent", adapter_type="mock")
    for pack_id in ("hr-v1", "hr-injection-v1"):
        pack = get_exam_pack(pack_id)
        competencies = [item.competency for item in pack.items]
        held = {competency: 0.4 for competency in competencies}
        run = RunRecord(id=f"run_sprite_{pack_id}", candidate_id=candidate.id, exam_pack_id=pack_id)
        scorecard = _scorecard(
            run.id,
            held=held,
            transfer_gap={competencies[0]: 0.5, **{c: 0.0 for c in competencies[1:]}},
            pass_at_k={c: False for c in competencies},
            certified=False,
            audit=TraceAuditSummary(status="unavailable", passes=False),
            failures=["failed"],
        )
        spec = build_agent_spec(run, candidate, scorecard, pack, [])
        for sub_agent in spec.sub_agents:
            assert sub_agent.sprite in _VALID_SPRITES, f"unknown sprite {sub_agent.sprite}"


def test_retained_lessons_flow_into_markdown() -> None:
    run = RunRecord(id="run_lessons", candidate_id="cand_l", exam_pack_id="hr-v1")
    candidate = CandidateConfig(id="cand_l", name="Learner", adapter_type="mock")
    pack = get_exam_pack("hr-v1")
    events = [
        RunEvent(
            run_id=run.id,
            sequence=1,
            actor="lesson_library",
            event_type="lesson_added",
            payload={"competency": "fairness", "lesson": "fairness: Treat equivalent candidates consistently."},
        ),
        RunEvent(
            run_id=run.id,
            sequence=2,
            actor="lesson_library",
            event_type="lesson_added",
            payload={"competency": "fairness", "lesson": "fairness: Treat equivalent candidates consistently."},
        ),
    ]
    scorecard = _scorecard(
        run.id,
        held={"fairness": 0.9},
        transfer_gap={"fairness": 0.0},
        pass_at_k={"fairness": True},
        certified=True,
        audit=_ok_audit(),
    )

    spec = build_agent_spec(run, candidate, scorecard, pack, events)

    # Duplicate lessons are de-duplicated.
    assert spec.agent_markdown.count("Treat equivalent candidates consistently.") == 1
