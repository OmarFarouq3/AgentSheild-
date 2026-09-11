"""HTTP middleware for request ids, timing, and request logging."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Awaitable

from fastapi import Request, Response

from agent_layer.config.logging import get_logger, reset_request_id, set_request_id

logger = get_logger(__name__)


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a request id to each request and include it in response headers."""

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = set_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
    except Exception:
        logger.exception("Unhandled request error")
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "HTTP request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "latency_ms": latency_ms,
            },
        )
        reset_request_id(token)
