from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from .database import database_backend_name, database_health
from .trace_audit import LOCAL_TRACERAZOR, _load_tracerazor_client


def connector_registry() -> list[dict[str, Any]]:
    supabase_ready = database_backend_name() == "supabase"
    hf_ready = shutil.which("hf") is not None
    agent_browser_ready = shutil.which("agent-browser") is not None
    return [
        {
            "id": "mock",
            "name": "Mock candidate",
            "status": "ready",
            "description": "Deterministic local candidate for demos and tests.",
            "config_schema": {"type": "object", "properties": {}},
        },
        {
            "id": "http",
            "name": "HTTP endpoint",
            "status": "ready",
            "description": "POSTs context and question to a candidate-owned endpoint.",
            "config_schema": {
                "type": "object",
                "required": ["endpoint_url"],
                "properties": {"endpoint_url": {"type": "string", "format": "uri"}},
            },
        },
        {
            "id": "supabase",
            "name": "Supabase Postgres",
            "status": "connected" if supabase_ready else "planned",
            "description": "Stores candidates, runs, scorecards, and trace events when Supabase is explicitly selected on the API process.",
            "config_schema": {
                "type": "object",
                "required": ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
                "properties": {
                    "SUPABASE_URL": {"type": "string", "format": "uri"},
                    "SUPABASE_SERVICE_ROLE_KEY": {"type": "string", "writeOnly": True},
                },
            },
        },
        {
            "id": "hugging-face",
            "name": "Hugging Face",
            "status": "ready" if hf_ready else "planned",
            "description": "Future exam-pack import and model-card connector using the `hf` CLI or Hub APIs.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "HF_TOKEN": {"type": "string", "writeOnly": True},
                    "dataset_id": {"type": "string"},
                    "model_id": {"type": "string"},
                },
            },
        },
        {
            "id": "vercel-agent-browser",
            "name": "Vercel agent-browser",
            "status": "ready" if agent_browser_ready else "planned",
            "description": "Browser automation connector for deployed or local workspace verification.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "session": {"type": "string"},
                },
            },
        },
        {
            "id": "openai-compatible",
            "name": "OpenAI-compatible model",
            "status": "planned",
            "description": "Provider adapter for model plus system-prompt candidates.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "base_url": {"type": "string"},
                    "model": {"type": "string"},
                    "system_prompt": {"type": "string"},
                },
            },
        },
        {
            "id": "local-command",
            "name": "Local command",
            "status": "planned",
            "description": "Runs a local executable candidate behind the same ask contract.",
            "config_schema": {
                "type": "object",
                "properties": {"command": {"type": "array", "items": {"type": "string"}}},
            },
        },
        {
            "id": "mcp-server",
            "name": "MCP server",
            "status": "planned",
            "description": "Wraps an MCP-hosted agent or tool server as a candidate adapter.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "server_url": {"type": "string"},
                    "tool_name": {"type": "string"},
                },
            },
        },
    ]


def connector_probes() -> list[dict[str, Any]]:
    """Read-only product probes for the tools Assay can use today."""

    return [
        _probe_mock(),
        _probe_http(),
        _probe_tracerazor(),
        _probe_supabase(),
        _probe_hugging_face(),
        _probe_agent_browser(),
        _planned_probe(
            "openai-compatible",
            "OpenAI-compatible model",
            "Provider candidate adapter is registry-ready. Add server-only API credentials before activation.",
        ),
        _planned_probe(
            "local-command",
            "Local command",
            "Command candidates are designed into the contract, but execution is intentionally disabled for this MVP.",
        ),
        _planned_probe(
            "mcp-server",
            "MCP server",
            "MCP candidate wrapping is a queued connector until a specific server and tool contract are chosen.",
        ),
    ]


def _server_supabase_key() -> str:
    return (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        or os.environ.get("SUPABASE_SECRET_KEY", "")
        or os.environ.get("SUPABASE_KEY", "")
    )


def _probe_mock() -> dict[str, Any]:
    return {
        "id": "mock",
        "name": "Mock candidate",
        "status": "pass",
        "evidence": "Deterministic adapter is built into the API test path.",
        "details": {"contract": "ask(context, question) -> CandidateResponse"},
        "next_step": None,
    }


def _probe_http() -> dict[str, Any]:
    return {
        "id": "http",
        "name": "HTTP endpoint",
        "status": "pass",
        "evidence": "HTTP adapter is available and shares the same examiner and grading pipeline as mock candidates.",
        "details": {"method": "POST", "requires": ["endpoint_url"]},
        "next_step": "Register a candidate endpoint with POST /candidates.",
    }


def _probe_tracerazor() -> dict[str, Any]:
    client = _load_tracerazor_client()
    if client is None:
        return {
            "id": "tracerazor",
            "name": "TraceRazor",
            "status": "fail",
            "evidence": f"TraceRazor is not importable from {LOCAL_TRACERAZOR} or the active Python environment.",
            "details": {"local_path": LOCAL_TRACERAZOR},
            "next_step": "Run scripts/setup.ps1 or install tracerazor>=1.0.3.",
        }
    return {
        "id": "tracerazor",
        "name": "TraceRazor",
        "status": "pass",
        "evidence": "TraceRazorClient imports and candidate-only audit traces can be scored.",
        "details": {"client": f"{client.__module__}.{client.__name__}", "local_path": LOCAL_TRACERAZOR},
        "next_step": None,
    }


def _probe_supabase() -> dict[str, Any]:
    url_configured = bool(os.environ.get("SUPABASE_URL"))
    key_configured = bool(_server_supabase_key())
    try:
        backend = database_backend_name()
        health = database_health()
    except Exception as exc:
        return {
            "id": "supabase",
            "name": "Supabase Postgres",
            "status": "fail",
            "evidence": f"Database probe failed: {exc}",
            "details": {"url_configured": url_configured, "server_key_configured": key_configured},
            "next_step": "Check server-only Supabase env vars and rerun python -m assay_api.verify_database.",
        }

    if backend == "supabase" and health.get("ok"):
        return {
            "id": "supabase",
            "name": "Supabase Postgres",
            "status": "pass",
            "evidence": "API is using Supabase persistence and table health returned ok.",
            "details": health,
            "next_step": None,
        }

    if url_configured and key_configured:
        evidence = "Supabase credentials are present, but SQLite is active because ASSAY_DB_BACKEND is not set to supabase."
    elif url_configured and not key_configured:
        evidence = "Supabase URL is configured, but the server-only service role key is missing."
    else:
        evidence = "SQLite fallback is active; Supabase migration files are present for server mode."
    return {
        "id": "supabase",
        "name": "Supabase Postgres",
        "status": "warn",
        "evidence": evidence,
        "details": health | {"url_configured": url_configured, "server_key_configured": key_configured},
        "next_step": "Set ASSAY_DB_BACKEND=supabase plus SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY on the API process to activate Supabase.",
    }


def _probe_hugging_face() -> dict[str, Any]:
    hf_path = shutil.which("hf")
    if hf_path is None:
        return {
            "id": "hugging-face",
            "name": "Hugging Face",
            "status": "warn",
            "evidence": "The hf CLI is not on PATH for this API process.",
            "details": {},
            "next_step": "Install or expose the hf CLI before enabling Hub-backed exam pack import.",
        }
    version = _run_command(["hf", "version"])
    auth = _run_command(["hf", "auth", "whoami"])
    auth_line = auth["stdout"] or auth["stderr"] or "auth state unavailable"
    auth_logged_in = auth["exit_code"] == 0 and "not logged in" not in auth_line.lower()
    status = "pass" if version["exit_code"] == 0 and auth_logged_in else "warn"
    return {
        "id": "hugging-face",
        "name": "Hugging Face",
        "status": status,
        "evidence": f"{version['stdout'] or 'hf CLI detected'}; auth: {auth_line}",
        "details": {"path": hf_path, "version": version, "auth": auth},
        "next_step": None if status == "pass" else "Run hf auth login or set HF_TOKEN before private Hub operations.",
    }


def _probe_agent_browser() -> dict[str, Any]:
    browser_path = shutil.which("agent-browser")
    if browser_path is None:
        return {
            "id": "vercel-agent-browser",
            "name": "Vercel agent-browser",
            "status": "warn",
            "evidence": "agent-browser is not on PATH; Playwright remains the current visual verifier.",
            "details": {"playwright": "apps/web/playwright.config.ts"},
            "next_step": "Install or expose agent-browser to use the Vercel browser automation connector.",
        }
    result = _run_command(["agent-browser", "--help"])
    return {
        "id": "vercel-agent-browser",
        "name": "Vercel agent-browser",
        "status": "pass" if result["exit_code"] == 0 else "warn",
        "evidence": result["stdout"] or result["stderr"] or "agent-browser command detected.",
        "details": {"path": browser_path, "help": result},
        "next_step": None if result["exit_code"] == 0 else "Check agent-browser installation.",
    }


def _planned_probe(connector_id: str, name: str, evidence: str) -> dict[str, Any]:
    return {
        "id": connector_id,
        "name": name,
        "status": "warn",
        "evidence": evidence,
        "details": {},
        "next_step": "Keep this connector disabled until a concrete candidate runtime is configured.",
    }


def _run_command(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": _trim(result.stdout),
            "stderr": _trim(result.stderr),
        }
    except Exception as exc:
        return {"command": command, "exit_code": -1, "stdout": "", "stderr": str(exc)}


def _trim(value: str, limit: int = 220) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."
