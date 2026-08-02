"""Authentication behaviour.

The properties asserted here are the ones whose absence would be a security
finding rather than a bug report.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.config import Settings
from api.dependencies.auth import CurrentUser
from tests.conftest import build_app


def _with_guarded_route(app: FastAPI) -> FastAPI:
    """Health is deliberately unguarded, so exercising require_auth needs a route."""

    @app.get("/api/v1/_guarded")
    def guarded(user: CurrentUser) -> dict[str, str]:
        return {"email": user.email, "subject": user.subject, "channel": user.channel}

    return app


def test_guarded_route_rejects_an_unauthenticated_request(settings: Settings) -> None:
    with TestClient(_with_guarded_route(build_app(settings))) as c:
        assert c.get("/api/v1/_guarded").status_code == 401


def test_a_garbage_assertion_is_rejected_and_never_echoed(settings: Settings) -> None:
    """A rejected bearer token in a response body lands in devtools, proxy
    access logs and any error-reporting SDK the frontend has installed."""
    token = "not.a.jwt-but-a-recognisable-secret-value"
    with TestClient(_with_guarded_route(build_app(settings))) as c:
        resp = c.get("/api/v1/_guarded", headers={"x-goog-iap-jwt-assertion": token})

    assert resp.status_code in (401, 503)
    assert token not in resp.text
    assert "secret-value" not in resp.text


def test_bypass_authenticates_an_allowlisted_identity(bypass_settings: Settings) -> None:
    with TestClient(_with_guarded_route(build_app(bypass_settings))) as c:
        resp = c.get(
            "/api/v1/_guarded",
            headers={"x-dev-auth-bypass": "test-secret", "x-dev-auth-email": "other@unops.org"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "other@unops.org"
    # A first-class channel, not a flag buried in claims: PM-7 requires every
    # audit record to name how the identity was established, and a bypassed
    # request must never look like a real session downstream.
    assert body["channel"] == "dev-bypass"
    assert body["subject"].startswith("dev-bypass:")


def test_bypass_refuses_an_identity_outside_the_allowlist(bypass_settings: Settings) -> None:
    """Otherwise a request header can forge any address at all, and the forged
    identity appears in the audit log indistinguishable from a real one."""
    with TestClient(_with_guarded_route(build_app(bypass_settings))) as c:
        resp = c.get(
            "/api/v1/_guarded",
            headers={
                "x-dev-auth-bypass": "test-secret",
                "x-dev-auth-email": "attacker@example.com",
            },
        )
    assert resp.status_code == 401


def test_bypass_ignores_a_wrong_secret(bypass_settings: Settings) -> None:
    """It never rejects — a wrong secret simply leaves the identity unset and
    the real assertion path runs, which then 401s."""
    with TestClient(_with_guarded_route(build_app(bypass_settings))) as c:
        resp = c.get(
            "/api/v1/_guarded",
            headers={"x-dev-auth-bypass": "wrong", "x-dev-auth-email": "dev@unops.org"},
        )
    assert resp.status_code == 401


def test_bypass_headers_do_nothing_when_the_gate_is_closed(settings: Settings) -> None:
    """The middleware is not even imported when disabled, so there is no code
    path for these headers to reach."""
    with TestClient(_with_guarded_route(build_app(settings))) as c:
        resp = c.get(
            "/api/v1/_guarded",
            headers={"x-dev-auth-bypass": "test-secret", "x-dev-auth-email": "dev@unops.org"},
        )
    assert resp.status_code == 401


def test_health_reports_the_bypass_when_it_is_on(bypass_settings: Settings) -> None:
    with TestClient(build_app(bypass_settings)) as c:
        assert c.get("/api/v1/health").json()["devAuthBypass"] is True
