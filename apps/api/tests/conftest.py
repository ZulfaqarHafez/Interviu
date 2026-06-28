from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERVIU_DB_PATH", str(tmp_path / "interviu-test.db"))
    monkeypatch.delenv("INTERVIU_DB_BACKEND", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from interviu_api.database import reset_store_cache
    from interviu_api import rate_limit as rl

    reset_store_cache()
    rl._storage.reset()
    rl._parsed_cache.clear()
    yield
    reset_store_cache()
    rl._storage.reset()
    rl._parsed_cache.clear()
