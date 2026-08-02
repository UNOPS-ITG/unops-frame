"""Request timing and an in-flight gauge.

Pure ASGI rather than ``BaseHTTPMiddleware``: the latter pipes every response
through an anyio memory stream, which buffers streaming responses and adds a
task group per request. Frame's realtime rooms (GR-8) stream, so that would be
a correctness problem and not only overhead.

Registered ABOVE the auth middleware so ``duration_ms`` includes the JWKS fetch
and JWT verification — the exact latency you most want visible on a cold
process.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

_in_flight = {"value": 0}


def get_in_flight_count() -> int:
    return _in_flight["value"]


class TimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500
        _in_flight["value"] += 1

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # In `finally` so an exception cannot leak the gauge — a counter
            # that only ever goes up is worse than no counter.
            _in_flight["value"] -= 1
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "method=%s path=%s status=%s duration_ms=%.1f in_flight=%s",
                scope.get("method"),
                scope.get("path"),
                status_code,
                duration_ms,
                _in_flight["value"],
            )
