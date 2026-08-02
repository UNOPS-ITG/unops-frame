"""Refuses oversized request bodies before anything expensive happens.

Outermost of Frame's own middleware, so an oversized body is rejected before
the auth middleware spends a JWKS fetch and a signature verification on it.

Both halves matter. The declared ``content-length`` is checked first because it
is free. But it is also client-supplied and may be absent entirely on a chunked
upload, so the streamed body is counted as it arrives and the request is cut off
the moment it exceeds the ceiling — otherwise a chunked request with no
content-length walks straight past a header-only check.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await self._too_large(scope, receive, send)
                    return
            except ValueError:
                pass  # malformed header; the streamed count below still applies

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Signal end-of-stream rather than raising: the handler sees a
                    # truncated body and the framework returns a clean 400 rather
                    # than an unhandled exception mid-parse.
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, counting_receive, send)

    async def _too_large(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            {"detail": f"Request body exceeds {self.max_bytes} bytes"},
            status_code=413,
        )
        await response(scope, receive, send)
