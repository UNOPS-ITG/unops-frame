"""Health endpoints. The only unauthenticated surface in Frame.

Three, because they answer different questions and conflating them causes real
outages:

* ``/live``   — is the process running? Never touches a dependency. A liveness
                probe that checks the database restarts a healthy process every
                time the database hiccups.
* ``/ready``  — can this instance serve traffic? Checks dependencies.
* ``/health`` — a human-readable summary for a developer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from api.dependencies.settings import AppSettings
from api.middleware.timing import get_in_flight_count

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response, settings: AppSettings) -> dict[str, Any]:
    checks: dict[str, str] = {}
    healthy = True

    try:
        # A metadata-only round trip: enough to prove credentials resolve and
        # the endpoint answers, without reading application data on every probe.
        import asyncio

        from lib.firestore import get_db

        await asyncio.to_thread(lambda: next(get_db().collections(), None))
        checks["firestore"] = "ok"
    except Exception as exc:  # noqa: BLE001 - a readiness probe reports, never raises
        checks["firestore"] = f"error: {type(exc).__name__}"
        healthy = False

    if not healthy:
        response.status_code = 503

    return {
        "status": "ok" if healthy else "degraded",
        "environment": settings.environment,
        "checks": checks,
        "inFlight": get_in_flight_count(),
    }


@router.get("")
def health(settings: AppSettings) -> dict[str, Any]:
    return {
        "service": "frame-api",
        "environment": settings.environment,
        "database": settings.firestore_database_id,
        "emulators": settings.emulators_active,
        # Surfaced deliberately. A bypass nobody notices is enabled is the
        # dangerous kind, and this is cheaper to check than reading logs.
        "devAuthBypass": settings.dev_auth_bypass_enabled,
    }
