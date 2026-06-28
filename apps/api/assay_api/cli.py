from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from .agent_intake import detect_agent_facts
from .agent_research import resolve_openai_key
from .database import (
    init_db,
    proof_bundle,
    reset_store_cache,
    save_candidate,
    save_run,
)
from .exam_packs import get_exam_pack, load_exam_pack_file, register_exam_pack
from .models import CandidateConfig, RunRecord
from .orchestrator import RunOrchestrator
from .tenancy import bind_tenant_id, reset_tenant_id


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_command(args)
    parser.print_help()
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assay",
        description="Run an Assay Assay evaluation from CI or a local shell.",
    )
    subparsers = parser.add_subparsers(dest="command")
    run = subparsers.add_parser("run", help="Run an agent.md against an exam pack")
    run.add_argument("--agent-md", required=True, help="Path to the agent.md or AGENTS.md file")
    run.add_argument("--pack", required=True, help="Exam pack id, for example hr-v1")
    run.add_argument("--pack-file", help="Optional JSON/YAML exam pack file to register before running")
    run.add_argument("--pass-threshold", type=float, default=0.8, help="Minimum mean competency score")
    run.add_argument("--k", type=int, default=1, help="Trials per seen/held-out item")
    run.add_argument("--db-path", help="SQLite database path for this run")
    run.add_argument("--json-out", help="Scorecard JSON output path")
    run.add_argument("--proof-out", help="Proof bundle JSON output path")
    run.add_argument("--summary-out", help="Markdown summary output path")
    run.add_argument("--tenant", default="local", help="Tenant id to stamp on persisted artifacts")
    run.add_argument("--live", action="store_true", help="Run the uploaded agent with OpenAI instead of mock mode")
    run.add_argument(
        "--require-trace",
        action="store_true",
        help="Fail when TraceRazor is unavailable or below threshold",
    )
    return parser


def _run_command(args: argparse.Namespace) -> int:
    if not 0 <= args.pass_threshold <= 1:
        print("--pass-threshold must be between 0 and 1", file=sys.stderr)
        return 2
    if args.k < 1 or args.k > 8:
        print("--k must be between 1 and 8", file=sys.stderr)
        return 2

    agent_path = Path(args.agent_md)
    if not agent_path.exists():
        print(f"agent markdown not found: {agent_path}", file=sys.stderr)
        return 2

    if args.db_path:
        os.environ["ASSAY_DB_PATH"] = str(Path(args.db_path))
        os.environ["ASSAY_DB_BACKEND"] = "sqlite"
        reset_store_cache()

    if not args.live:
        os.environ["ASSAY_DISABLE_OPENAI"] = "1"
    elif not resolve_openai_key():
        print("--live requires OPENAI_API_KEY (or openai_key) to be configured", file=sys.stderr)
        return 2

    try:
        token = bind_tenant_id(args.tenant)
    except Exception:
        print("--tenant must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$", file=sys.stderr)
        return 2
    try:
        return asyncio.run(_run_async(args, agent_path))
    except KeyError:
        print(f"exam pack not found: {args.pack}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"assay run errored: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        reset_tenant_id(token)


async def _run_async(args: argparse.Namespace, agent_path: Path) -> int:
    if args.pack_file:
        register_exam_pack(load_exam_pack_file(args.pack_file))

    pack = get_exam_pack(args.pack)
    markdown = agent_path.read_text(encoding="utf-8")
    detected = detect_agent_facts(markdown)
    init_db()

    live = bool(args.live)
    candidate = CandidateConfig(
        name=detected["title"] or agent_path.stem,
        adapter_type="openai-compatible" if live else "mock",
        system_prompt=markdown,
        metadata={"source": "assay-cli", **detected},
    )
    candidate = save_candidate(candidate)
    run = save_run(
        RunRecord(
            candidate_id=candidate.id,
            exam_pack_id=pack.id,
            k=args.k,
            competency_threshold=args.pass_threshold,
        )
    )

    scorecard = await RunOrchestrator().start(run, candidate)
    bundle = proof_bundle(run.id)
    if bundle is None:
        raise RuntimeError("proof bundle was not available after run completion")

    out_dir = Path("artifacts") / "assay"
    json_out = Path(args.json_out) if args.json_out else out_dir / f"{run.id}-scorecard.json"
    proof_out = Path(args.proof_out) if args.proof_out else out_dir / f"{run.id}-proof-bundle.json"
    summary_out = Path(args.summary_out) if args.summary_out else out_dir / f"{run.id}-summary.md"

    score_payload = _score_payload(scorecard.model_dump(mode="json"), args.pass_threshold, args.require_trace)
    _write_json(json_out, score_payload)
    _write_json(proof_out, bundle)

    summary = _markdown_summary(score_payload, proof_out)
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\nScorecard JSON: {json_out}")
    print(f"Proof bundle JSON: {proof_out}")

    return 0 if score_payload["passed"] else 1


def _score_payload(scorecard: dict[str, Any], pass_threshold: float, require_trace: bool) -> dict[str, Any]:
    competency_scores = scorecard.get("competency_scores") or {}
    values = [float(value) for value in competency_scores.values()]
    mean_score = round(mean(values), 3) if values else 0.0
    trace_status = ((scorecard.get("trace_audit") or {}).get("status") or "pending")
    trace_passes = bool((scorecard.get("trace_audit") or {}).get("passes"))
    competencies_pass = mean_score >= pass_threshold
    failures = scorecard.get("failure_reasons") or []
    blocking_failures = [
        reason
        for reason in failures
        if require_trace or not str(reason).startswith("TraceRazor ")
    ]
    certified = bool(scorecard.get("certified"))
    passed = competencies_pass and not blocking_failures
    return {
        "schema": "assay.scorecard.v1",
        "run_id": scorecard.get("run_id"),
        "passed": passed,
        "certified": certified,
        "pass_threshold": pass_threshold,
        "mean_competency_score": mean_score,
        "trace_required": require_trace,
        "trace_status": trace_status,
        "trace_passes": trace_passes,
        "failure_reasons": failures,
        "blocking_failure_reasons": blocking_failures,
        "scorecard": scorecard,
    }


def _markdown_summary(payload: dict[str, Any], proof_out: Path) -> str:
    verdict = "PASS" if payload["passed"] else "FAIL"
    lines = [
        f"# Assay verdict: {verdict}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Run | `{payload['run_id']}` |",
        f"| Mean competency score | {payload['mean_competency_score']:.3f} |",
        f"| Threshold | {payload['pass_threshold']:.3f} |",
        f"| Certified | {'yes' if payload['certified'] else 'no'} |",
        f"| Trace | {payload['trace_status']} ({'required' if payload['trace_required'] else 'non-blocking'}) |",
        f"| Proof bundle | `{proof_out}` |",
    ]
    failures = payload.get("failure_reasons") or []
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- {reason}" for reason in failures)
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
