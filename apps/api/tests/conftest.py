from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSAY_DB_PATH", str(tmp_path / "assay-test.db"))
    monkeypatch.delenv("ASSAY_DB_BACKEND", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("ASSAY_REQUIRE_TENANT", raising=False)
    monkeypatch.delenv("ASSAY_DEFAULT_TENANT", raising=False)
    from assay_api.database import reset_store_cache
    from assay_api import rate_limit as rl

    reset_store_cache()
    rl._storage.reset()
    rl._parsed_cache.clear()
    yield
    reset_store_cache()
    rl._storage.reset()
    rl._parsed_cache.clear()
