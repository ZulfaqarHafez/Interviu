from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException, Request, status
from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting is on by default with generous limits. Set
# ASSAY_RATE_LIMIT_ENABLED=0/false/off to disable it for local troubleshooting.
RATE_LIMIT_ENABLED_ENV = "ASSAY_RATE_LIMIT_ENABLED"

# Per-endpoint limits, each tunable via env. Defaults are generous so normal
# interactive use is never throttled; they exist to blunt abuse/runaway clients.
_LIMIT_ENVS: dict[str, tuple[str, str]] = {
    "create_run": ("ASSAY_RATE_LIMIT_CREATE_RUN", "600/minute"),
    "start_run": ("ASSAY_RATE_LIMIT_START_RUN", "300/minute"),
    "role_analysis": ("ASSAY_RATE_LIMIT_ROLE_ANALYSIS", "300/minute"),
    "agent_research": ("ASSAY_RATE_LIMIT_AGENT_RESEARCH", "120/minute"),
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _falsy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"0", "false", "no", "off"}


def rate_limiting_enabled() -> bool:
    raw = os.environ.get(RATE_LIMIT_ENABLED_ENV)
    if raw is None or not raw.strip():
        return True
    if _falsy(raw):
        return False
    return _truthy(raw)


def limit_for(name: str) -> str:
    env_name, default = _LIMIT_ENVS[name]
    return os.environ.get(env_name, "").strip() or default


# A slowapi ``Limiter`` is wired into ``app.state`` (slowapi reads it there and it
# provides the storage/strategy machinery this module builds on). We drive the
# actual per-endpoint checks through a FastAPI dependency below — that keeps
# request-body forward-ref resolution intact under ``from __future__ import
# annotations`` (the ``@limiter.limit`` decorator wraps the endpoint and breaks
# FastAPI's ability to resolve Pydantic body models).
limiter = Limiter(
    key_func=get_remote_address,
    enabled=rate_limiting_enabled(),
    default_limits=[],
)

_storage = MemoryStorage()
_strategy = MovingWindowRateLimiter(_storage)
_parsed_cache: dict[str, RateLimitItem] = {}


def _parsed_limit(name: str) -> RateLimitItem:
    spec = limit_for(name)
    item = _parsed_cache.get(spec)
    if item is None:
        item = parse(spec)
        _parsed_cache[spec] = item
    return item


def rate_limit(name: str) -> Callable[[Request], None]:
    """Build a FastAPI dependency enforcing the named limit per client address."""

    def dependency(request: Request) -> None:
        if not rate_limiting_enabled():
            return
        item = _parsed_limit(name)
        identifier = get_remote_address(request)
        if not _strategy.hit(item, name, identifier):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(item.get_expiry())},
            )

    return dependency
