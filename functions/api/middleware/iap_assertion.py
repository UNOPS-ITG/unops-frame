"""Validates the signed identity assertion. The only authentication code in Frame.

There is deliberately **no `if local:` branch**. Locally the assertion is a
Google OIDC id_token injected by oauth2-proxy (iss ``accounts.google.com``,
RS256, keys from Google's OAuth certs); deployed it is a Cloud IAP assertion
(iss ``https://cloud.google.com/iap``, ES256, keys from gstatic). Three
configuration values differ and the code does not, so the path exercised on a
laptop is the path that runs in production.

It does not reject *unauthenticated* requests — it either populates
``scope["state"]["auth"]`` or leaves it unset, and rejection is centralised in
``api.dependencies.auth.require_auth``. That way health endpoints exist without
an exemption list living in two places. It does reject a **present but invalid**
assertion, because a bad token must never fall through to be retried as
something else.
"""

from __future__ import annotations

import asyncio
import base64
import calendar
import email.utils
import json
import logging
import time
from typing import Any

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from api.core.config import Settings, get_settings
from api.core.identity import AuthContext

logger = logging.getLogger(__name__)

ASSERTION_HEADER = "x-goog-iap-jwt-assertion"

# ONE copy of this allowlist, deliberately. A security-relevant exemption list
# that exists in two modules will drift, and the drift is invisible until an
# endpoint is unauthenticated.
SKIP_AUTH_PATHS = frozenset(
    {"/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"}
)


class _AssertionRejected(Exception):
    """Anything that makes an otherwise well-formed assertion unacceptable."""


def _peek_kid(token: str) -> str | None:
    """Read ``kid`` from the UNVERIFIED header.

    Safe because it is used only to select which public key to verify against,
    never to make a trust decision. If it is wrong, verification fails.
    """
    try:
        header_b64 = token.split(".", 1)[0]
        padding = "=" * (-len(header_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(header_b64 + padding)).get("kid")
    except Exception:
        return None


class _JwksCache:
    """Single-flight JWKS cache with stale fallback and rotation-aware refresh."""

    def __init__(self, url: str, default_ttl: int = 3600) -> None:
        self._url = url
        self._default_ttl = default_ttl
        self._keys: dict[str, Any] | None = None
        self._expires_at = 0.0
        self._last_forced = 0.0
        self._lock = asyncio.Lock()

    async def get(self, http: httpx.AsyncClient, kid: str | None) -> KeySet:
        now = time.time()
        cached = self._keys
        if cached is not None and now < self._expires_at and self._has(cached, kid):
            return KeySet.import_key_set(cached)  # fast path, no lock

        async with self._lock:
            now = time.time()
            cached = self._keys
            if cached is not None and now < self._expires_at and self._has(cached, kid):
                return KeySet.import_key_set(cached)  # re-check inside the lock

            # A kid miss against a still-valid cache means the signing key
            # rotated. Refresh — but at most once a minute, so a garbage kid
            # cannot be used to hammer the JWKS endpoint.
            if cached is not None and now < self._expires_at and now - self._last_forced < 60:
                return KeySet.import_key_set(cached)
            self._last_forced = now

            try:
                resp = await http.get(self._url, timeout=5.0)
                resp.raise_for_status()
                payload = dict(resp.json())
            except Exception as exc:
                logger.error("JWKS fetch failed (%s): %s", self._url, exc)
                if cached is not None:
                    return KeySet.import_key_set(cached)  # stale beats unavailable
                raise

            self._keys = payload
            self._expires_at = now + self._ttl(resp.headers, now)
            return KeySet.import_key_set(payload)

    @staticmethod
    def _has(jwk_set: dict[str, Any], kid: str | None) -> bool:
        if kid is None:
            return True
        return any(k.get("kid") == kid for k in jwk_set.get("keys", []))

    def _ttl(self, headers: httpx.Headers, now: float) -> float:
        cache_control = headers.get("cache-control", "")
        for part in (p.strip() for p in cache_control.split(",")):
            if part.startswith("max-age="):
                try:
                    return max(60.0, float(part.split("=", 1)[1]))
                except ValueError:
                    pass
        expires = headers.get("expires")
        if expires:
            try:
                # parsedate_to_datetime returns a timezone-AWARE datetime and
                # timegm then treats it as UTC. Parsing with strptime("%Z") and
                # time.mktime instead reads a GMT timestamp as LOCAL time, so on
                # any non-UTC machine the cache expires hours early or late.
                parsed = email.utils.parsedate_to_datetime(expires)
                return max(60.0, calendar.timegm(parsed.utctimetuple()) - now)
            except (TypeError, ValueError):
                pass
        return float(self._default_ttl)


class IapAssertionMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        self.app = app
        self.settings = settings or get_settings()

        # FAIL CLOSED. Disabling validation with a log warning when the audience
        # is unset would leave authentication depending on every endpoint
        # remembering to declare a dependency. Frame's API is GENERATED — a
        # generator bug emitting a route without it would be silently
        # unauthenticated. Refuse to start instead.
        if not self.settings.iap_audience:
            raise RuntimeError(
                "iap_audience is not configured. Refusing to start: an empty audience "
                "would disable assertion validation entirely. Locally, set it to the "
                "Google OAuth client id that oauth2-proxy is configured with."
            )

        self._claims = JWTClaimsRegistry(
            # joserfc defaults to leeway=0, so exp/nbf/iat are checked with zero
            # clock-skew tolerance — which produces intermittent, unreproducible
            # 401s on any laptop or container whose clock has drifted a second.
            leeway=60,
            iss={"essential": True, "value": self.settings.iap_issuer},
            aud={"essential": True, "value": self.settings.iap_audience},
            exp={"essential": True},
        )
        self._jwks = _JwksCache(self.settings.iap_jwks_url)
        # An explicit algorithm allowlist is what prevents `alg: none` and
        # HMAC-confusion attacks. Never omit it, never widen it.
        self._algorithms = ["ES256", "RS256"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)  # websocket, lifespan
            return

        state = scope.setdefault("state", {})
        if scope["path"] in SKIP_AUTH_PATHS or state.get("auth") is not None:
            # state["auth"] already set means the dev bypass resolved it.
            await self.app(scope, receive, send)
            return

        assertion = Headers(scope=scope).get(ASSERTION_HEADER)
        if not assertion:
            await self.app(scope, receive, send)  # require_auth will 401
            return

        http: httpx.AsyncClient | None = getattr(scope["app"].state, "http", None)
        if http is None:
            await self._reject(503, "Identity verification unavailable", scope, receive, send)
            return

        kid = _peek_kid(assertion)
        try:
            key_set = await self._jwks.get(http, kid)
            token = jwt.decode(assertion, key_set, algorithms=self._algorithms)
            claims = dict(token.claims)
            self._claims.validate(claims)
            self._assert_acceptable_identity(claims)
        except (JoseError, _AssertionRejected) as exc:
            # NEVER echo the assertion back. A rejected bearer token in a
            # response body lands in devtools, proxy access logs and any
            # error-reporting SDK the frontend happens to have installed.
            logger.warning("assertion rejected: kid=%s reason=%s", kid, exc)
            await self._reject(401, "Invalid authentication assertion", scope, receive, send)
            return
        except Exception:
            logger.exception("assertion verification failed unexpectedly")
            # 503, not 401: "we could not check" and "we checked and you may
            # not" are different facts, and reporting the second sends a user
            # to reset a password that was never the problem.
            await self._reject(503, "Identity verification unavailable", scope, receive, send)
            return

        state["auth"] = AuthContext(
            subject=str(claims["sub"]),
            email=str(claims["email"]),
            email_verified=bool(claims.get("email_verified", False)),
            name=claims.get("name"),
            picture=claims.get("picture"),
            channel="iap",
            auth_time=claims.get("auth_time"),
            claims=claims,
        )
        await self.app(scope, receive, send)

    def _assert_acceptable_identity(self, claims: dict[str, Any]) -> None:
        """Domain restriction lives HERE, not only at the proxy.

        Locally the trust anchor is accounts.google.com with a public OAuth
        client id as the audience, so without this check the backend would
        accept an id_token minted for that client by *any* Google account. The
        proxy's own domain restriction only protects traffic that goes through
        the proxy, and the dev-bypass harness is proof that people reach the
        backend port directly.
        """
        if not claims.get("sub"):
            raise _AssertionRejected("no sub claim")
        if not claims.get("email"):
            raise _AssertionRejected("no email claim")
        if claims.get("email_verified") is not True:
            raise _AssertionRejected("email_verified is not true")

        domain = self.settings.identity_hosted_domain
        if domain:
            hosted = claims.get("hd") or str(claims["email"]).rsplit("@", 1)[-1]
            if hosted.lower() != domain.lower():
                raise _AssertionRejected("hosted domain mismatch")

    @staticmethod
    async def _reject(
        status: int, detail: str, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
