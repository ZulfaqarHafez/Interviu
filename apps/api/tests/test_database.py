from __future__ import annotations

import json

import pytest

from assay_api.database import SupabaseStore, database_backend_name, reset_store_cache, store


def test_default_database_backend_is_sqlite() -> None:
    assert database_backend_name() == "sqlite"
    assert store().health()["ok"] is True


def test_supabase_env_without_backend_flag_keeps_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-key")
    reset_store_cache()

    assert database_backend_name() == "sqlite"


def test_forced_supabase_requires_server_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSAY_DB_BACKEND", "supabase")
    reset_store_cache()

    with pytest.raises(RuntimeError):
        store()


def test_supabase_store_builds_rows_without_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict, str]] = []

    class FakeTable:
        def __init__(self, table: str):
            self.table = table

        def upsert(self, row: dict, on_conflict: str):
            calls.append((self.table, row, on_conflict))
            return self

        def select(self, *_args, **_kwargs):
            return self

        def limit(self, _limit: int):
            return self

        def execute(self):
            return type("Response", (), {"data": [], "count": 0})()

    class FakeClient:
        def table(self, table: str):
            return FakeTable(table)

    def fake_create_client(url: str, key: str):
        assert url == "https://project.supabase.co"
        assert key == "server-key"
        return FakeClient()

    monkeypatch.setitem(__import__("sys").modules, "supabase", type("FakeSupabase", (), {"create_client": fake_create_client}))
    store_instance = SupabaseStore("https://project.supabase.co", "server-key")

    from assay_api.models import CandidateConfig

    store_instance.save_candidate(CandidateConfig(id="cand_x", name="Demo", adapter_type="mock"))

    assert calls[0][0] == "assay_candidates"
    assert calls[0][1]["id"] == "cand_x"
    assert calls[0][2] == "id"
    assert store_instance.health()["backend"] == "supabase"


def test_sqlite_lessons_round_trip() -> None:
    from assay_api.database import get_lesson, init_db, list_lessons_for_candidate, save_lesson
    from assay_api.models import DiagnosticLesson

    init_db()
    lesson = DiagnosticLesson(
        candidate_id="cand_1",
        exam_pack_id="hr-v1",
        competency="compliance",
        text="needs work",
        origin_run_id="run_1",
        origin_score=0.2,
    )
    save_lesson(lesson)

    fetched = get_lesson(lesson.id)
    assert fetched is not None
    assert fetched.competency == "compliance"
    assert fetched.active is True

    scoped = list_lessons_for_candidate("cand_1", "hr-v1", ["compliance"], active_only=True)
    assert len(scoped) == 1

    # Retiring a lesson removes it from the active view but keeps the record.
    lesson.active = False
    save_lesson(lesson)
    assert list_lessons_for_candidate("cand_1", active_only=True) == []
    assert len(list_lessons_for_candidate("cand_1", active_only=False)) == 1


def test_sqlite_quarantines_legacy_private_http_candidate() -> None:
    from assay_api.database import init_db, list_candidates

    init_db()
    store_instance = store()
    payload = {
        "id": "cand_legacy",
        "tenant_id": "local",
        "name": "Legacy HTTP",
        "adapter_type": "http",
        "endpoint_url": "http://127.0.0.1:8080/ask",
        "metadata": {},
    }
    with store_instance.connect() as conn:
        conn.execute(
            "INSERT INTO candidates (id, tenant_id, payload, created_at) VALUES (?, ?, ?, ?)",
            ("cand_legacy", "local", json.dumps(payload), "2026-01-01T00:00:00+00:00"),
        )

    candidate = next(item for item in list_candidates() if item.id == "cand_legacy")

    assert candidate.endpoint_url is None
    assert candidate.metadata["quarantined_endpoint_url"] == "http://127.0.0.1:8080/ask"


def test_supabase_store_persists_lessons(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict, str]] = []

    class FakeQuery:
        def __init__(self, table: str):
            self.table = table

        def upsert(self, row: dict, on_conflict: str):
            calls.append((self.table, row, on_conflict))
            return self

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def in_(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return type("Response", (), {"data": [], "count": 0})()

    class FakeClient:
        def table(self, table: str):
            return FakeQuery(table)

    monkeypatch.setitem(
        __import__("sys").modules,
        "supabase",
        type("FakeSupabase", (), {"create_client": lambda url, key: FakeClient()}),
    )
    store_instance = SupabaseStore("https://project.supabase.co", "server-key")

    from assay_api.models import DiagnosticLesson

    store_instance.save_lesson(
        DiagnosticLesson(
            candidate_id="cand_x",
            exam_pack_id="hr-v1",
            competency="compliance",
            text="t",
            origin_run_id="run_1",
        )
    )

    table, row, on_conflict = calls[0]
    assert table == "assay_lessons"
    assert row["candidate_id"] == "cand_x"
    assert row["exam_pack_id"] == "hr-v1"
    assert row["competency"] == "compliance"
    assert row["active"] is True
    assert on_conflict == "id"

    # The filtered list path executes its query chain without error.
    assert store_instance.list_lessons_for_candidate("cand_x", "hr-v1", ["compliance"]) == []
