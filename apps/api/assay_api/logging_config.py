from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

LOGGER_NAME = "assay"
REQUEST_ID_HEADER = "X-Request-ID"

# Context var so log records emitted while handling a request can carry its id
# without threading it through every call.
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "assay_request_id", default=None
)


def current_request_id() -> str | None:
    return request_id_ctx.get()


class _JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for structured ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or current_request_id()
        if request_id:
            payload["request_id"] = request_id
        for key in ("method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging() -> logging.Logger:
    """Configure the ``assay`` logger once with a JSON stream handler.

    Idempotent so repeated app construction (e.g. across tests) does not stack
    duplicate handlers. Level is tunable via ``ASSAY_LOG_LEVEL`` (default INFO).
    """

    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger

    level_name = os.environ.get("ASSAY_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    _configured = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign/propagate a request id and emit a structured access log line."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid4().hex
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id
        logger = get_logger()
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
