"""Local-only authentication bypass.

Exists because oauth2-proxy drives an interactive Google consent screen that a
headless agent cannot complete. Firestore access stays real — against the
emulator — so this is not a mock of the data path, only of the identity one.

Three independent gates, any one of which fails closed:

1. ``Settings.dev_auth_bypass_enabled`` — a secret is configured AND the
   environment is LOCAL AND ``K_SERVICE`` is absent. The module is not even
   *imported* otherwise, so in a deployed process there is no code path at all.
2. The secret lives in ``config/.env``, which is gitignored and per-machine.
3. Per request, a constant-time comparison, and the impersonated identity must
   be on an allowlist.

It never rejects. A wrong secret simply leaves ``state["auth"]`` unset and the
real assertion path runs. It works by pre-populating ``state["auth"]``, which
trips the pass-through in ``IapAssertionMiddleware`` — that is its entire
integration contract, and it is why this middleware must be registered LAST so
that it EXECUTES FIRST.
"""

from __future__ import annotations

import hmac
import logging

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from api.core.config import Settings, get_settings
from api.core.identity import AuthContext

logger = logging.getLogger(__name__)


class DevAuthBypassMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        self.app = app
        self.settings = settings or get_settings()
        self._allowed = self._allowed_identities(self.settings)

        # A bypass nobody notices is enabled is the dangerous kind. Also
        # surfaced by the health endpoint so it is visible without reading logs.
        logger.warning(
            "DEV AUTH BYPASS ENABLED — local only. Allowed identities: %s",
            ", ".join(sorted(self._allowed)) or "(none configured — bypass will reject)",
        )

    @staticmethod
    def _allowed_identities(settings: Settings) -> set[str]:
        allowed = {e.strip().lower() for e in settings.dev_auth_bypass_allowed_emails if e.strip()}
        if settings.dev_auth_bypass_default_email:
            allowed.add(settings.dev_auth_bypass_default_email.strip().lower())
        return allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        presented = headers.get("x-dev-auth-bypass")
        secret = self.settings.dev_auth_bypass_secret

        if presented and secret and hmac.compare_digest(presented, secret):
            requested = (
                headers.get("x-dev-auth-email") or self.settings.dev_auth_bypass_default_email
            ).strip().lower()

            # Pinned, not arbitrary. Letting a request header name any address
            # at all means local runs can forge an identity that then appears in
            # an audit log indistinguishable from a real one.
            if requested and requested in self._allowed:
                scope.setdefault("state", {})["auth"] = AuthContext(
                    subject=f"dev-bypass:{requested}",
                    email=requested,
                    email_verified=True,
                    channel="dev-bypass",
                    claims={"email": requested, "dev_bypass": True},
                )
                logger.warning("DEV AUTH BYPASS: authenticated as %s", requested)
            else:
                logger.warning(
                    "DEV AUTH BYPASS: refused identity %r (not in the allowlist)", requested
                )

        await self.app(scope, receive, send)
