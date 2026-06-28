from __future__ import annotations

import contextvars
import os
import re
from collections.abc import AsyncIterator

from fastapi import Header, HTTPException, Request, status

from .security import EXEMPT_PATHS, configured_api_keys

TENANT_HEADER = "X-Assay-Tenant"
DEFAULT_TENANT_ENV = "ASSAY_DEFAULT_TENANT"
REQUIRE_TENANT_ENV = "ASSAY_REQUIRE_TENANT"

_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_tenant_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "assay_tenant_id",
    default="",
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def tenant_required() -> bool:
    return _truthy(os.environ.get(REQUIRE_TENANT_ENV))


def default_tenant_id() -> str:
    tenant_id = os.environ.get(DEFAULT_TENANT_ENV, "local").strip() or "local"
    if not _TENANT_ID_RE.fullmatch(tenant_id):
        return "local"
    return tenant_id


def current_tenant_id() -> str:
    return _tenant_ctx.get() or default_tenant_id()


def bind_tenant_id(tenant_id: str) -> contextvars.Token[str]:
    return _tenant_ctx.set(validate_tenant_id(tenant_id))


def reset_tenant_id(token: contextvars.Token[str]) -> None:
    _tenant_ctx.reset(token)


def validate_tenant_id(value: str) -> str:
    tenant_id = value.strip()
    if not _TENANT_ID_RE.fullmatch(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant id",
        )
    return tenant_id


async def require_tenant(
    request: Request,
    x_assay_tenant: str | None = Header(default=None, alias=TENANT_HEADER),
) -> AsyncIterator[None]:
    """Bind the request to a tenant.

    Local mode remains frictionless: with no tenant header and no required mode,
    all reads/writes are scoped to the built-in ``local`` tenant. Hosted mode can
    set ``ASSAY_REQUIRE_TENANT=1`` to require an explicit tenant header on all
    non-health routes; API-key auth is still handled by ``require_api_key``.
    """

    if request.url.path in EXEMPT_PATHS:
        yield
        return

    if tenant_required():
        if not configured_api_keys():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tenant mode requires ASSAY_API_KEYS to be configured",
            )
        if not x_assay_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing {TENANT_HEADER}",
            )

    tenant_id = validate_tenant_id(x_assay_tenant) if x_assay_tenant else default_tenant_id()
    request.state.tenant_id = tenant_id
    token = bind_tenant_id(tenant_id)
    try:
        yield
    finally:
        _tenant_ctx.reset(token)
