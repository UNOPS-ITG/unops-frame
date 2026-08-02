"""Mints or propagates the request correlation id.

Registered above the auth middleware so that even a 401 log line carries an id
— a rejected request is often exactly the one somebody needs to trace.

An inbound ``x-correlation-id`` is honoured so a trace survives a hop from the
frontend or another service, but it is length-capped and character-filtered:
the value ends up in log lines and audit records, and an unbounded
client-controlled string in a log is a log-injection vector.
"""

from __future__ import annotations

import re

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.core.correlation import (
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

HEADER = "x-correlation-id"
_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class CorrelationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = Headers(scope=scope).get(HEADER)
        correlation_id = inbound if inbound and _SAFE.match(inbound) else new_correlation_id()

        token = set_correlation_id(correlation_id)
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        async def send_wrapper(message: Message) -> None:
            # Echo it back so a caller can quote the id when reporting a problem.
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(HEADER, correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            reset_correlation_id(token)
