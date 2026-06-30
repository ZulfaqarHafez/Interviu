from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from ..agent_refinery import agent_spec_payload
from ..agent_research import research_agent_spec
from ..connectors import connector_probes, connector_registry
from ..database import (
    database_health,
    get_candidate,
    get_lesson,
    get_run,
    get_scorecard,
    list_events,
    list_runs,
    proof_bundle,
    save_run,
    trace_payload,
)
from ..exam_packs import get_exam_pack
from ..exports import write_agent_spec_files
from ..models import RunCreate, RunRecord
from ..orchestrator import RunOrchestrator
from ..product_review import product_review_for_run
from ..progress import candidate_progress, lesson_library, run_comparison
from ..rate_limit import rate_limit
from ..role_intelligence import analyze_job_scope, role_analysis_for_run

router = APIRouter()


@router.get("/runs")
def runs() -> list[dict]:
    # Enrich each run with a lightweight scorecard summary so the Experiments
    # table renders verdict/score without an N+1 per-row scorecard fetch.
    items: list[dict] = []
    for run in list_runs():
        item = run.model_dump(mode="json")
        if run.status == "completed":
            scorecard = get_scorecard(run.id)
            if scorecard is not None:
                passes = scorecard.pass_at_k or {}
                item["certified"] = scorecard.certified
                item["pass_count"] = sum(1 for v in passes.values() if v)
                item["total_count"] = len(passes)
                item["degraded"] = scorecard.degraded
                item["qualification_status"] = scorecard.qualification_status
                item["role_brief_summary"] = scorecard.role_brief_summary
        items.append(item)
    return items


@router.post("/runs", dependencies=[Depends(rate_limit("create_run"))])
def create_run(payload: RunCreate) -> dict:
    if get_candidate(payload.candidate_id) is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if payload.baseline_run_id is not None:
        if get_run(payload.baseline_run_id) is None:
            raise HTTPException(status_code=404, detail="Baseline run not found")
        if get_scorecard(payload.baseline_run_id) is None:
            raise HTTPException(status_code=409, detail="Baseline run has no scorecard yet")
    try:
        get_exam_pack(payload.exam_pack_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Exam pack not found") from exc

    exam_pack_id = payload.exam_pack_id
    # When the caller leaves the default pack, let role intelligence pick the pack
    # that best fits the supplied job scope.
    if payload.job_scope is not None and exam_pack_id == "hr-v1":
        exam_pack_id = analyze_job_scope(payload.job_scope).recommended_exam_pack_id

    # Live (OpenAI) candidates fire k x items x 2 LLM calls per run; on a
    # rate-limited free-tier key that is slow. ASSAY_LIVE_K caps attempts for
    # live candidates only (mock/deterministic runs and tests are untouched).
    effective_k = payload.k
    live_k_env = os.environ.get("ASSAY_LIVE_K", "").strip()
    if live_k_env:
        candidate = get_candidate(payload.candidate_id)
        if candidate is not None and candidate.adapter_type == "openai-compatible":
            try:
                effective_k = max(1, min(payload.k, int(live_k_env)))
            except ValueError:
                pass

    run = RunRecord(
        candidate_id=payload.candidate_id,
        exam_pack_id=exam_pack_id,
        k=effective_k,
        competency_threshold=payload.competency_threshold,
        max_transfer_gap=payload.max_transfer_gap,
        tas_threshold=payload.tas_threshold,
        job_scope=payload.job_scope,
        baseline_run_id=payload.baseline_run_id,
    )
    return save_run(run).model_dump(mode="json")


@router.post("/runs/{run_id}/start", dependencies=[Depends(rate_limit("start_run"))])
async def start_run(run_id: str) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    candidate = get_candidate(run.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if run.status == "completed":
        scorecard = get_scorecard(run.id)
        return scorecard.model_dump(mode="json") if scorecard else run.model_dump(mode="json")
    scorecard = await RunOrchestrator().start(run, candidate)
    return scorecard.model_dump(mode="json")


@router.get("/runs/{run_id}")
def get_run_endpoint(run_id: str) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.model_dump(mode="json")


@router.get("/runs/{run_id}/role-analysis")
def run_role_analysis(run_id: str) -> dict:
    payload = role_analysis_for_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return payload


@router.get("/runs/{run_id}/role-brief")
def run_role_brief(run_id: str) -> dict:
    """The role brief the judge was qualified with, if the run produced one.

    Reads the persisted ``role_qualified`` event rather than re-running research,
    so it is free and reflects exactly what graded this run.
    """
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    for event in reversed(list_events(run_id)):
        if event.event_type == "role_qualified":
            return event.payload
    raise HTTPException(status_code=404, detail="Role brief not found for this run")


@router.get("/runs/{run_id}/events")
def run_events(run_id: str) -> list[dict]:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return [event.model_dump(mode="json") for event in list_events(run_id)]


@router.get("/runs/{run_id}/scorecard")
def run_scorecard(run_id: str) -> dict:
    scorecard = get_scorecard(run_id)
    if scorecard is None:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return scorecard.model_dump(mode="json")


@router.get("/runs/{run_id}/reviewers")
def run_reviewers(run_id: str) -> dict:
    payload = product_review_for_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return payload.model_dump(mode="json")


@router.get("/runs/{run_id}/trace")
def run_trace(run_id: str) -> dict:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace_payload(run_id)


@router.get("/runs/{run_id}/comparison")
def run_comparison_endpoint(run_id: str, baseline: str | None = None) -> dict:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    payload = run_comparison(run_id, baseline)
    if payload is None:
        raise HTTPException(status_code=409, detail="Run has no scorecard yet; start the run first")
    return payload.model_dump(mode="json")


@router.get("/runs/{run_id}/lessons-applied")
def run_lessons_applied(run_id: str) -> list[dict]:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    scorecard = get_scorecard(run_id)
    if scorecard is None:
        return []
    resolved = [get_lesson(lesson_id) for lesson_id in scorecard.lessons_applied]
    return [lesson.model_dump(mode="json") for lesson in resolved if lesson is not None]


@router.get("/runs/{run_id}/agent-spec")
def run_agent_spec(run_id: str) -> dict:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        payload = agent_spec_payload(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="Run references an unregistered exam pack") from exc
    if payload is None:
        raise HTTPException(status_code=409, detail="Run has no scorecard yet; start the run first")
    return payload


@router.post("/runs/{run_id}/agent-spec/export-files")
def export_agent_spec_files(run_id: str) -> dict:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        export = write_agent_spec_files(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="Run references an unregistered exam pack") from exc
    if export is None:
        raise HTTPException(status_code=409, detail="Run has no scorecard yet; start the run first")
    return export.model_dump(mode="json")


@router.post(
    "/runs/{run_id}/agent-spec/research",
    dependencies=[Depends(rate_limit("agent_research"))],
)
def run_agent_research(run_id: str, mode: str = "fast") -> dict:
    if mode not in ("fast", "deep"):
        raise HTTPException(status_code=422, detail="mode must be 'fast' or 'deep'")
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        research = research_agent_spec(run_id, mode)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="Run references an unregistered exam pack") from exc
    if research is None:
        raise HTTPException(status_code=409, detail="Run has no scorecard yet; start the run first")
    return research.model_dump(mode="json")


@router.get("/runs/{run_id}/proof-bundle")
def run_proof_bundle(run_id: str) -> dict:
    bundle = proof_bundle(run_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        db_health = database_health()
    except Exception as exc:
        db_health = {"ok": False, "error": str(exc)}
    try:
        agent_spec = agent_spec_payload(run_id)
    except KeyError:
        agent_spec = None
    try:
        role_analysis_bundle = role_analysis_for_run(run_id)
    except Exception:
        role_analysis_bundle = None
    run_record = get_run(run_id)
    progress_bundle = None
    diagnostic_library: list[dict] = []
    if run_record is not None:
        progress_payload = candidate_progress(run_record.candidate_id)
        progress_bundle = progress_payload.model_dump(mode="json") if progress_payload else None
        diagnostic_library = [
            lesson.model_dump(mode="json") for lesson in lesson_library(run_record.candidate_id)
        ]
    return bundle | {
        "database": db_health,
        "connectors": connector_registry(),
        "connector_probes": connector_probes(),
        "agent_spec": agent_spec,
        "role_analysis": role_analysis_bundle,
        "candidate_progress": progress_bundle,
        "diagnostic_library": diagnostic_library,
    }
