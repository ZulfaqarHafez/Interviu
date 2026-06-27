from __future__ import annotations

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import CandidateConfig, RunEvent, RunRecord, Scorecard, utc_now


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "interviu.db"


class DataStore(ABC):
    name: str

    @abstractmethod
    def init(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_candidate(self, candidate: CandidateConfig) -> CandidateConfig:
        raise NotImplementedError

    @abstractmethod
    def list_candidates(self) -> list[CandidateConfig]:
        raise NotImplementedError

    @abstractmethod
    def get_candidate(self, candidate_id: str) -> CandidateConfig | None:
        raise NotImplementedError

    @abstractmethod
    def save_run(self, run: RunRecord) -> RunRecord:
        raise NotImplementedError

    @abstractmethod
    def list_runs(self) -> list[RunRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord | None:
        raise NotImplementedError

    @abstractmethod
    def save_event(self, event: RunEvent) -> RunEvent:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, run_id: str) -> list[RunEvent]:
        raise NotImplementedError

    @abstractmethod
    def save_scorecard(self, scorecard: Scorecard) -> Scorecard:
        raise NotImplementedError

    @abstractmethod
    def get_scorecard(self, run_id: str) -> Scorecard | None:
        raise NotImplementedError


class SQLiteStore(DataStore):
    name = "sqlite"

    def __init__(self, path: Path | None = None):
        self.path = path or db_path()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    exam_pack_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    span_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_run_sequence
                ON events(run_id, sequence);

                CREATE TABLE IF NOT EXISTS scorecards (
                    run_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def health(self) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            candidates = conn.execute("SELECT COUNT(*) AS count FROM candidates").fetchone()["count"]
            runs = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]
        return {
            "backend": self.name,
            "ok": True,
            "path": str(self.path),
            "tables": {
                "candidates": candidates,
                "runs": runs,
            },
        }

    def save_candidate(self, candidate: CandidateConfig) -> CandidateConfig:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO candidates (id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (candidate.id, _dump_model(candidate), candidate.created_at.isoformat()),
            )
        return candidate

    def list_candidates(self) -> list[CandidateConfig]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload FROM candidates ORDER BY created_at DESC").fetchall()
        return [CandidateConfig.model_validate_json(row["payload"]) for row in rows]

    def get_candidate(self, candidate_id: str) -> CandidateConfig | None:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        return CandidateConfig.model_validate_json(row["payload"]) if row else None

    def save_run(self, run: RunRecord) -> RunRecord:
        run.updated_at = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs
                (id, candidate_id, exam_pack_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.candidate_id,
                    run.exam_pack_id,
                    run.status,
                    _dump_model(run),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
        return run

    def list_runs(self) -> list[RunRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload FROM runs ORDER BY created_at DESC").fetchall()
        return [RunRecord.model_validate_json(row["payload"]) for row in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return RunRecord.model_validate_json(row["payload"]) if row else None

    def save_event(self, event: RunEvent) -> RunEvent:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO events (span_id, run_id, sequence, payload)
                VALUES (?, ?, ?, ?)
                """,
                (event.span_id, event.run_id, event.sequence, _dump_model(event)),
            )
        return event

    def list_events(self, run_id: str) -> list[RunEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM events WHERE run_id = ? ORDER BY sequence ASC",
                (run_id,),
            ).fetchall()
        return [RunEvent.model_validate_json(row["payload"]) for row in rows]

    def save_scorecard(self, scorecard: Scorecard) -> Scorecard:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scorecards (run_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (scorecard.run_id, _dump_model(scorecard), scorecard.created_at.isoformat()),
            )
        return scorecard

    def get_scorecard(self, run_id: str) -> Scorecard | None:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM scorecards WHERE run_id = ?", (run_id,)).fetchone()
        return Scorecard.model_validate_json(row["payload"]) if row else None


class SupabaseStore(DataStore):
    name = "supabase"

    tables = {
        "candidates": "interviu_candidates",
        "runs": "interviu_runs",
        "events": "interviu_events",
        "scorecards": "interviu_scorecards",
    }

    def __init__(self, url: str, key: str):
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("Install the 'supabase' Python package to use Supabase persistence.") from exc
        self.client = create_client(url, key)

    def init(self) -> None:
        # Supabase schema is managed by supabase/migrations/*.sql.
        self.client.table(self.tables["candidates"]).select("id").limit(1).execute()

    def health(self) -> dict[str, Any]:
        table_status: dict[str, Any] = {}
        for logical_name, table in self.tables.items():
            response = self.client.table(table).select("*", count="exact").limit(1).execute()
            table_status[logical_name] = {
                "table": table,
                "count": response.count,
            }
        return {
            "backend": self.name,
            "ok": True,
            "tables": table_status,
        }

    def save_candidate(self, candidate: CandidateConfig) -> CandidateConfig:
        self._upsert(
            self.tables["candidates"],
            {
                "id": candidate.id,
                "payload": candidate.model_dump(mode="json"),
                "created_at": candidate.created_at.isoformat(),
            },
            "id",
        )
        return candidate

    def list_candidates(self) -> list[CandidateConfig]:
        rows = self._select(self.tables["candidates"], order="created_at", desc=True)
        return [CandidateConfig.model_validate(row["payload"]) for row in rows]

    def get_candidate(self, candidate_id: str) -> CandidateConfig | None:
        row = self._single(self.tables["candidates"], "id", candidate_id)
        return CandidateConfig.model_validate(row["payload"]) if row else None

    def save_run(self, run: RunRecord) -> RunRecord:
        run.updated_at = utc_now()
        self._upsert(
            self.tables["runs"],
            {
                "id": run.id,
                "candidate_id": run.candidate_id,
                "exam_pack_id": run.exam_pack_id,
                "status": run.status,
                "payload": run.model_dump(mode="json"),
                "created_at": run.created_at.isoformat(),
                "updated_at": run.updated_at.isoformat(),
            },
            "id",
        )
        return run

    def list_runs(self) -> list[RunRecord]:
        rows = self._select(self.tables["runs"], order="created_at", desc=True)
        return [RunRecord.model_validate(row["payload"]) for row in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._single(self.tables["runs"], "id", run_id)
        return RunRecord.model_validate(row["payload"]) if row else None

    def save_event(self, event: RunEvent) -> RunEvent:
        self._upsert(
            self.tables["events"],
            {
                "span_id": event.span_id,
                "run_id": event.run_id,
                "sequence": event.sequence,
                "payload": event.model_dump(mode="json"),
                "created_at": event.started_at.isoformat(),
            },
            "span_id",
        )
        return event

    def list_events(self, run_id: str) -> list[RunEvent]:
        response = (
            self.client.table(self.tables["events"])
            .select("payload")
            .eq("run_id", run_id)
            .order("sequence")
            .execute()
        )
        return [RunEvent.model_validate(row["payload"]) for row in response.data or []]

    def save_scorecard(self, scorecard: Scorecard) -> Scorecard:
        self._upsert(
            self.tables["scorecards"],
            {
                "run_id": scorecard.run_id,
                "payload": scorecard.model_dump(mode="json"),
                "created_at": scorecard.created_at.isoformat(),
            },
            "run_id",
        )
        return scorecard

    def get_scorecard(self, run_id: str) -> Scorecard | None:
        row = self._single(self.tables["scorecards"], "run_id", run_id)
        return Scorecard.model_validate(row["payload"]) if row else None

    def _upsert(self, table: str, row: dict[str, Any], on_conflict: str) -> None:
        self.client.table(table).upsert(row, on_conflict=on_conflict).execute()

    def _select(self, table: str, order: str, desc: bool = False) -> list[dict[str, Any]]:
        response = self.client.table(table).select("payload").order(order, desc=desc).execute()
        return response.data or []

    def _single(self, table: str, column: str, value: str) -> dict[str, Any] | None:
        response = self.client.table(table).select("payload").eq(column, value).limit(1).execute()
        rows = response.data or []
        return rows[0] if rows else None


def db_path() -> Path:
    return Path(os.environ.get("INTERVIU_DB_PATH", DEFAULT_DB_PATH))


def database_backend_name() -> str:
    return store().name


def database_configured() -> bool:
    try:
        store()
        return True
    except Exception:
        return False


def database_health() -> dict[str, Any]:
    return store().health()


def init_db() -> None:
    store().init()


def save_candidate(candidate: CandidateConfig) -> CandidateConfig:
    return store().save_candidate(candidate)


def list_candidates() -> list[CandidateConfig]:
    return store().list_candidates()


def get_candidate(candidate_id: str) -> CandidateConfig | None:
    return store().get_candidate(candidate_id)


def save_run(run: RunRecord) -> RunRecord:
    return store().save_run(run)


def list_runs() -> list[RunRecord]:
    return store().list_runs()


def get_run(run_id: str) -> RunRecord | None:
    return store().get_run(run_id)


def save_event(event: RunEvent) -> RunEvent:
    return store().save_event(event)


def list_events(run_id: str) -> list[RunEvent]:
    return store().list_events(run_id)


def save_scorecard(scorecard: Scorecard) -> Scorecard:
    return store().save_scorecard(scorecard)


def get_scorecard(run_id: str) -> Scorecard | None:
    return store().get_scorecard(run_id)


def trace_payload(run_id: str) -> dict[str, Any]:
    events = [event.model_dump(mode="json") for event in list_events(run_id)]
    scorecard = get_scorecard(run_id)
    return {
        "run_id": run_id,
        "events": events,
        "scorecard": scorecard.model_dump(mode="json") if scorecard else None,
    }


def proof_bundle(run_id: str) -> dict[str, Any] | None:
    run = get_run(run_id)
    if run is None:
        return None
    candidate = get_candidate(run.candidate_id)
    scorecard = get_scorecard(run_id)
    events = [event.model_dump(mode="json") for event in list_events(run_id)]
    return {
        "schema": "interviu.proof_bundle.v1",
        "product": "Interviu",
        "generated_at": utc_now().isoformat(),
        "run": run.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json") if candidate else None,
        "scorecard": scorecard.model_dump(mode="json") if scorecard else None,
        "events": events,
        "summary": {
            "status": run.status,
            "certified": scorecard.certified if scorecard else False,
            "certificate_label": scorecard.certificate_label if scorecard else "Internal capability bar only",
            "tas_score": scorecard.trace_audit.tas_score if scorecard else None,
            "trace_status": scorecard.trace_audit.status if scorecard else "pending",
            "event_count": len(events),
        },
    }


@lru_cache(maxsize=1)
def store() -> DataStore:
    backend = os.environ.get("INTERVIU_DB_BACKEND", "").strip().lower()
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if backend == "supabase" or (supabase_url and supabase_key):
        if not supabase_url or not supabase_key:
            raise RuntimeError("Supabase persistence requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return SupabaseStore(supabase_url, supabase_key)
    return SQLiteStore()


def reset_store_cache() -> None:
    store.cache_clear()


def _dump_model(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=True)
