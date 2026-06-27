from __future__ import annotations

import pytest

from interviu_api.database import SupabaseStore, database_backend_name, reset_store_cache, store


def test_default_database_backend_is_sqlite() -> None:
    assert database_backend_name() == "sqlite"
    assert store().health()["ok"] is True


def test_forced_supabase_requires_server_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_DB_BACKEND", "supabase")
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

    from interviu_api.models import CandidateConfig

    store_instance.save_candidate(CandidateConfig(id="cand_x", name="Demo", adapter_type="mock"))

    assert calls[0][0] == "interviu_candidates"
    assert calls[0][1]["id"] == "cand_x"
    assert calls[0][2] == "id"
    assert store_instance.health()["backend"] == "supabase"
