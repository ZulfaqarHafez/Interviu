from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, Request, status

API_KEY_HEADER = "X-API-Key"
API_KEYS_ENV = "ASSAY_API_KEYS"

# Paths that must always be reachable without a key (health probes / preflight).
EXEMPT_PATHS = {"/health", "/health/database"}


def configured_api_keys() -> set[str]:
    """Return the set of accepted API keys parsed from ``ASSAY_API_KEYS``.

    The env var is a comma-separated list. Empty/whitespace entries are dropped.
    When unset or empty the returned set is empty, which means auth is disabled
    (open access, matching the prototype's default behaviour).
    """

    raw = os.environ.get(API_KEYS_ENV, "")
    return {key.strip() for key in raw.split(",") if key.strip()}


def _key_matches(candidate: str, accepted: set[str]) -> bool:
    # Constant-time comparison against each accepted key to avoid timing leaks.
    return any(hmac.compare_digest(candidate, key) for key in accepted)


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> None:
    """Global auth dependency.

    Opt-in: if ``ASSAY_API_KEYS`` is unset/empty this is a no-op so the local
    dev app keeps working with no auth configured. When keys are configured, a
    matching ``X-API-Key`` header is required or the request is rejected with 401.
    Health probes (see ``EXEMPT_PATHS``) are always allowed.
    """

    accepted = configured_api_keys()
    if not accepted:
        return
    if request.url.path in EXEMPT_PATHS:
        return
    if x_api_key is None or not _key_matches(x_api_key, accepted):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
