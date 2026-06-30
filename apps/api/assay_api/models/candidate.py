from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ..network_guard import validate_http_candidate_endpoint
from ..tenancy import current_tenant_id
from ._common import (
    AdapterType,
    _MAX_CANDIDATE_ANSWER_CHARS,
    _MAX_CANDIDATE_REASONING_CHARS,
    _MAX_TOOL_CALLS,
    _MAX_TOOL_PARAM_BYTES,
    _MAX_TOOL_TEXT_CHARS,
    _TENANT_ID_PATTERN,
    utc_now,
)


class ToolCall(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)
    output: str | None = Field(default=None, max_length=_MAX_TOOL_TEXT_CHARS)
    success: bool = True
    error: str | None = Field(default=None, max_length=_MAX_TOOL_TEXT_CHARS)
    tokens: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("params")
    @classmethod
    def _cap_params(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, default=str, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            encoded = str(value).encode("utf-8")
        if len(encoded) > _MAX_TOOL_PARAM_BYTES:
            raise ValueError(f"tool params exceed {_MAX_TOOL_PARAM_BYTES} byte limit")
        return value


class TokenCounts(BaseModel):
    input: int = Field(default=0, ge=0)
    output: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class ToolSpec(BaseModel):
    """A tool/function the agent under test can call. Parsed from the user's
    `tools.py` (signatures + docstrings) or supplied as an OpenAI function schema.
    `parameters` is a JSON Schema object ready to hand to OpenAI function-calling.
    """
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    description: str = Field(default="", max_length=2000)
    signature: str = Field(default="", max_length=400)
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    dangerous: bool = False

    model_config = ConfigDict(extra="forbid")

    def to_openai_tool(self) -> dict[str, Any]:
        """Shape for the Responses API `tools=[...]` parameter."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description or self.signature or self.name,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }


class CandidateConfig(BaseModel):
    id: str = Field(default_factory=lambda: f"cand_{uuid4().hex[:10]}")
    tenant_id: str = Field(default_factory=current_tenant_id, pattern=_TENANT_ID_PATTERN)
    name: str
    adapter_type: AdapterType = "mock"
    endpoint_url: HttpUrl | None = None
    model: str | None = None
    system_prompt: str | None = None
    command: list[str] | None = None
    mcp_server_url: HttpUrl | None = None
    tools: list[ToolSpec] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(extra="forbid")

    @field_validator("endpoint_url")
    @classmethod
    def _reject_private_endpoint(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None:
            validate_http_candidate_endpoint(value)
        return value


class CandidateResponse(BaseModel):
    answer: str = Field(max_length=_MAX_CANDIDATE_ANSWER_CHARS)
    reasoning: str = Field(default="", max_length=_MAX_CANDIDATE_REASONING_CHARS)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=_MAX_TOOL_CALLS)
    latency_ms: int = Field(default=0, ge=0)
    tokens: TokenCounts = Field(default_factory=TokenCounts)

    model_config = ConfigDict(extra="forbid")
