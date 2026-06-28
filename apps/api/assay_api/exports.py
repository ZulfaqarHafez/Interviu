from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_refinery import load_agent_spec
from .exam_packs import exam_pack_export
from .models import AgentSpecFileExport, ExamPackFileExport

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPORT_ROOT = PROJECT_ROOT / "exports" / "exam-packs"
AGENT_EXPORT_ROOT = PROJECT_ROOT / "exports" / "agents"


def write_exam_pack_files(pack_id: str) -> ExamPackFileExport:
    payload = exam_pack_export(pack_id)
    pack = payload["pack"]
    hf = payload["huggingface"]
    rows: list[dict[str, Any]] = hf["files"]["data/assay_exam_rows.jsonl"]
    slug = _safe_slug(pack["id"])
    directory = EXPORT_ROOT / slug
    data_dir = directory / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "data/assay_exam_rows.jsonl": data_dir / "assay_exam_rows.jsonl",
        "README.md": directory / "README.md",
        "assay-exam-pack.json": directory / "assay-exam-pack.json",
    }
    files["data/assay_exam_rows.jsonl"].write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    files["README.md"].write_text(hf["files"]["README.md"], encoding="utf-8")
    files["assay-exam-pack.json"].write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return ExamPackFileExport(
        pack_id=pack["id"],
        directory=str(directory),
        files={name: str(path) for name, path in files.items()},
        row_count=len(rows),
        suggested_commands=_local_hf_commands(pack["id"], directory),
    )


def write_agent_spec_files(run_id: str) -> AgentSpecFileExport | None:
    spec = load_agent_spec(run_id)
    if spec is None:
        return None
    slug = _safe_slug(spec.run_id)
    directory = AGENT_EXPORT_ROOT / slug
    sub_dir = directory / "subagents"
    sub_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, Path] = {
        "AGENTS.md": directory / "AGENTS.md",
        "agent-spec.json": directory / "agent-spec.json",
    }
    files["AGENTS.md"].write_text(spec.agent_markdown, encoding="utf-8")
    files["agent-spec.json"].write_text(
        json.dumps({"schema": "assay.agent_spec.v1", **spec.model_dump(mode="json")}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    for sub_agent in spec.sub_agents:
        name = f"subagents/{_safe_slug(sub_agent.id)}.md"
        path = sub_dir / f"{_safe_slug(sub_agent.id)}.md"
        path.write_text(sub_agent.definition_markdown, encoding="utf-8")
        files[name] = path

    return AgentSpecFileExport(
        run_id=spec.run_id,
        directory=str(directory),
        files={name: str(path) for name, path in files.items()},
        sub_agent_count=len(spec.sub_agents),
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
