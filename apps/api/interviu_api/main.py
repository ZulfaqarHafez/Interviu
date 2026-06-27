from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
from .exam_packs import exam_pack_export, get_exam_pack, list_exam_packs, register_exam_pack
from .exports import write_exam_pack_files
from .models import CandidateConfig, ExamPack, RunCreate, RunRecord
from .orchestrator import RunOrchestrator
from .trace_audit import _load_tracerazor_client

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
    init_db()
    if not list_candidates():
        save_candidate(CandidateConfig(name="Demo Candidate", adapter_type="mock"))


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
    run = RunRecord(
        candidate_id=payload.candidate_id,
        exam_pack_id=payload.exam_pack_id,
        k=payload.k,
        competency_threshold=payload.competency_threshold,
        max_transfer_gap=payload.max_transfer_gap,
        tas_threshold=payload.tas_threshold,
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


@app.get("/runs/{run_id}/proof-bundle")
def run_proof_bundle(run_id: str) -> dict:
    bundle = proof_bundle(run_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        db_health = database_health()
    except Exception as exc:
        db_health = {"ok": False, "error": str(exc)}
    return bundle | {
        "database": db_health,
        "connectors": connector_registry(),
        "connector_probes": connector_probes(),
    }
