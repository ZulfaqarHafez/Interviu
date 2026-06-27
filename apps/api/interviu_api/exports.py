from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .exam_packs import exam_pack_export
from .models import ExamPackFileExport

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPORT_ROOT = PROJECT_ROOT / "exports" / "exam-packs"


def write_exam_pack_files(pack_id: str) -> ExamPackFileExport:
    payload = exam_pack_export(pack_id)
    pack = payload["pack"]
    hf = payload["huggingface"]
    rows: list[dict[str, Any]] = hf["files"]["data/interviu_exam_rows.jsonl"]
    slug = _safe_slug(pack["id"])
    directory = EXPORT_ROOT / slug
    data_dir = directory / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "data/interviu_exam_rows.jsonl": data_dir / "interviu_exam_rows.jsonl",
        "README.md": directory / "README.md",
        "interviu-exam-pack.json": directory / "interviu-exam-pack.json",
    }
    files["data/interviu_exam_rows.jsonl"].write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    files["README.md"].write_text(hf["files"]["README.md"], encoding="utf-8")
    files["interviu-exam-pack.json"].write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return ExamPackFileExport(
        pack_id=pack["id"],
        directory=str(directory),
        files={name: str(path) for name, path in files.items()},
        row_count=len(rows),
        suggested_commands=_local_hf_commands(pack["id"], directory),
    )


def _local_hf_commands(pack_id: str, directory: Path) -> list[str]:
    repo = f"<namespace>/{pack_id}"
    return [
        "hf auth login",
        f"hf repo create {repo} --repo-type=dataset --exist-ok",
        f"hf upload {repo} {directory} . --repo-type=dataset",
    ]


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    if not slug:
        raise ValueError("Exam pack id cannot be used as an export directory.")
    return slug[:80]
