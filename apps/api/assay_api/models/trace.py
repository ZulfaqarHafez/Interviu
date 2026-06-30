from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TraceAuditSummary(BaseModel):
    status: Literal["ok", "insufficient_steps", "unavailable", "error"]
    trace_id: str | None = None
    tas_score: float | None = None
    grade: str | None = None
    passes: bool = False
    total_steps: int = 0
    total_tokens: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    savings: dict[str, Any] = Field(default_factory=dict)
    fixes: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
