"""The middleware stack, and the properties that make it safe.

The ordering here is not stylistic. Starlette's ``add_middleware`` prepends, so
registration order is the reverse of execution order — an easy thing to get
backwards, and getting it backwards silently disables the dev bypass or times
requests without their auth cost.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.core.config import Environment, Settings
from tests.conftest import build_app


def test_health_is_reachable_without_authentication(client: TestClient) -> None:
    """The only unauthenticated surface. It exists by NOT declaring the auth
    dependency, rather than by appearing on an exemption list in middleware."""
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_health_reports_that_the_bypass_is_off(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["devAuthBypass"] is False


def test_correlation_id_is_returned_on_every_response(client: TestClient) -> None:
    assert client.get("/api/v1/health/live").headers.get("x-correlation-id")


def test_inbound_correlation_id_is_propagated(client: TestClient) -> None:
    resp = client.get("/api/v1/health/live", headers={"x-correlation-id": "trace-abc123"})
    assert resp.headers["x-correlation-id"] == "trace-abc123"


def test_hostile_correlation_id_is_replaced_not_echoed(client: TestClient) -> None:
    """The value lands in log lines and audit records. An unbounded
    client-controlled string in a log is a log-injection vector."""
    hostile = "abc\r\nX-Injected: yes"
    resp = client.get("/api/v1/health/live", headers={"x-correlation-id": hostile})
    assert resp.headers["x-correlation-id"] != hostile
    assert "X-Injected" not in resp.headers


def test_oversized_body_is_refused(settings: Settings) -> None:
    small = settings.model_copy(update={"max_body_bytes": 512})
    with TestClient(build_app(small)) as c:
        resp = c.post("/api/v1/health", content=b"x" * 4096)
        assert resp.status_code == 413


def test_refuses_to_start_without_an_audience() -> None:
    """Fail closed. Disabling assertion validation with a warning would leave
    authentication depending on every generated route declaring a dependency."""
    blind = Settings(environment=Environment.LOCAL, iap_audience="")
    with pytest.raises(RuntimeError, match="iap_audience"):
        build_app(blind)


def test_bypass_middleware_is_absent_when_the_gate_is_closed(settings: Settings) -> None:
    app = build_app(settings)
    names = [m.cls.__name__ for m in app.user_middleware]
    assert "DevAuthBypassMiddleware" not in names
    assert "IapAssertionMiddleware" in names


def test_bypass_middleware_runs_outside_the_assertion_check(bypass_settings: Settings) -> None:
    """It works by pre-setting state["auth"], which trips the pass-through in
    the assertion middleware. Registered below it, the assertion check would
    already have run and the bypass would do nothing."""
    app = build_app(bypass_settings)
    names = [m.cls.__name__ for m in app.user_middleware]

    assert "DevAuthBypassMiddleware" in names
    # user_middleware is outermost-first, so the bypass must appear BEFORE the
    # assertion middleware in this list.
    assert names.index("DevAuthBypassMiddleware") < names.index("IapAssertionMiddleware")


def test_middleware_order_outermost_to_innermost(bypass_settings: Settings) -> None:
    app = build_app(bypass_settings)
    names = [m.cls.__name__ for m in app.user_middleware]
    assert names == [
        "CORSMiddleware",
        "BodySizeLimitMiddleware",
        "CorrelationMiddleware",
        "TimingMiddleware",
        "DevAuthBypassMiddleware",
        "IapAssertionMiddleware",
    ]
