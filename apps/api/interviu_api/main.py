from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .connectors import connector_probes, connector_registry
from .database import (
    database_health,
    database_backend_name,
    get_candidate,
    get_run,
    get_scorecard,
    init_db,
    list_candidates,
    list_events,
    list_runs,
    proof_bundle,
    save_candidate,
    save_run,
    trace_payload,
)
from .agent_refinery import agent_spec_payload
from .agent_research import load_local_env, research_agent_spec
from .exam_packs import exam_pack_export, get_exam_pack, list_exam_packs, register_exam_pack
from .exports import write_agent_spec_files, write_exam_pack_files
from .models import CandidateConfig, ExamPack, JobScope, RunCreate, RunRecord
from .orchestrator import RunOrchestrator
from .role_intelligence import (
    analyze_job_scope,
    extract_job_scope_openai,
    role_analysis_for_run,
    role_analysis_payload,
)
from .trace_audit import _load_tracerazor_client

_MAX_ROLE_SCOPE_CHARS = 8000

class RoleAnalysisRequest(BaseModel):
    raw_text: str = Field(default="", max_length=_MAX_ROLE_SCOPE_CHARS)
    extract: Literal["keyword", "openai-fast", "openai-deep"] = "keyword"
    override_pack_id: str | None = None


app = FastAPI(title="Interviu API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):30\d{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    load_local_env()
    init_db()
    candidates = list_candidates()
    if not candidates:
        save_candidate(CandidateConfig(name="Demo Candidate", adapter_type="mock"))
        return
    for candidate in candidates:
        if candidate.adapter_type == "mock" and candidate.name == "Demo HR Agent" and not candidate.metadata:
            save_candidate(candidate.model_copy(update={"name": "Demo Candidate"}))


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "interviu-api",
        "database_backend": database_backend_name(),
        "tracerazor_importable": _load_tracerazor_client() is not None,
    }


@app.get("/health/database")
def health_database() -> dict[str, object]:
    try:
        return database_health()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/exam-packs")
def exam_packs() -> list[dict]:
    return [pack.model_dump(mode="json") for pack in list_exam_packs()]


@app.post("/exam-packs/import")
def import_exam_pack(pack: ExamPack) -> dict:
    try:
        registered = register_exam_pack(pack)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return registered.model_dump(mode="json")


@app.get("/exam-packs/{pack_id}/export")
def export_exam_pack(pack_id: str) -> dict:
    try:
        return exam_pack_export(pack_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Exam pack not found") from exc


@app.post("/exam-packs/{pack_id}/export-files")
def export_exam_pack_files(pack_id: str) -> dict:
    try:
        return write_exam_pack_files(pack_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Exam pack not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/role-analysis")
def role_analysis(request: RoleAnalysisRequest) -> dict:
    raw_text = (request.raw_text or "")[:_MAX_ROLE_SCOPE_CHARS]
    if request.override_pack_id is not None:
        try:
            get_exam_pack(request.override_pack_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Exam pack not found") from exc

    job_scope: JobScope | None = None
    if request.extract != "keyword":
        mode = "deep" if request.extract == "openai-deep" else "fast"
        try:
            job_scope = extract_job_scope_openai(raw_text, mode=mode)
        except Exception:
            # OpenAI extraction is best-effort recall; fall back to keyword.
            job_scope = None
    if job_scope is None:
        job_scope = JobScope(raw_text=raw_text)

    return role_analysis_payload(job_scope, override_pack_id=request.override_pack_id)


@app.get("/connectors")
def connectors() -> list[dict]:
    return connector_registry()


@app.get("/connectors/probe")
def connectors_probe() -> list[dict]:
    return connector_probes()


@app.get("/candidates")
def candidates() -> list[dict]:
    return [candidate.model_dump(mode="json") for candidate in list_candidates()]


@app.post("/candidates")
def create_candidate(candidate: CandidateConfig) -> dict:
    return save_candidate(candidate).model_dump(mode="json")


@app.get("/runs")
def runs() -> list[dict]:
    return [run.model_dump(mode="json") for run in list_runs()]


@app.post("/runs")
def create_run(payload: RunCreate) -> dict:
    if get_candidate(payload.candidate_id) is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        get_exam_pack(payload.exam_pack_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Exam pack not found") from exc

    exam_pack_id = payload.exam_pack_id
    # When the caller leaves the default pack, let role intelligence pick the pack
    # that best fits the supplied job scope.
    if payload.job_scope is not None and exam_pack_id == "hr-v1":
        exam_pack_id = analyze_job_scope(payload.job_scope).recommended_exam_pack_id

    run = RunRecord(
        candidate_id=payload.candidate_id,
        exam_pack_id=exam_pack_id,
        k=payload.k,
        competency_threshold=payload.competency_threshold,
        max_transfer_gap=payload.max_transfer_gap,
        tas_threshold=payload.tas_threshold,
        job_scope=payload.job_scope,
    )
    return save_run(run).model_dump(mode="json")


@app.post("/runs/{run_id}/start")
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


@app.get("/runs/{run_id}")
def get_run_endpoint(run_id: str) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.model_dump(mode="json")


@app.get("/runs/{run_id}/role-analysis")
def run_role_analysis(run_id: str) -> dict:
    payload = role_analysis_for_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return payload


@app.get("/runs/{run_id}/events")
def run_events(run_id: str) -> list[dict]:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return [event.model_dump(mode="json") for event in list_events(run_id)]


@app.get("/runs/{run_id}/scorecard")
def run_scorecard(run_id: str) -> dict:
    scorecard = get_scorecard(run_id)
    if scorecard is None:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return scorecard.model_dump(mode="json")


@app.get("/runs/{run_id}/trace")
def run_trace(run_id: str) -> dict:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace_payload(run_id)


@app.get("/runs/{run_id}/agent-spec")
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


@app.post("/runs/{run_id}/agent-spec/export-files")
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


@app.post("/runs/{run_id}/agent-spec/research")
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


@app.get("/runs/{run_id}/proof-bundle")
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
    return bundle | {
        "database": db_health,
        "connectors": connector_registry(),
        "connector_probes": connector_probes(),
        "agent_spec": agent_spec,
        "role_analysis": role_analysis_bundle,
    }
