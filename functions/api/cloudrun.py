"""Process entrypoint.

Every step here is ordering discipline, and every one is load-bearing.
"""

from __future__ import annotations

import os

# 1. Load .env FIRST, before importing anything that reads settings at import time.
from dotenv import load_dotenv

load_dotenv("config/.env")

import uvicorn  # noqa: E402

from api.core.config import get_settings  # noqa: E402

settings = get_settings()

# 2. Round-trip the emulator hosts back into os.environ.
#
#    pydantic-settings READING a variable does not put it back, and the Google
#    SDKs look these up in the process environment rather than in any settings
#    object. Miss this and the client silently talks to the real cloud — which
#    on a laptop means an auth error, and in CI means writing to a real project.
if settings.firestore_emulator_host:
    os.environ["FIRESTORE_EMULATOR_HOST"] = settings.firestore_emulator_host
if settings.pubsub_emulator_host:
    os.environ["PUBSUB_EMULATOR_HOST"] = settings.pubsub_emulator_host
if settings.firebase_auth_emulator_host:
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.firebase_auth_emulator_host
if settings.firebase_storage_emulator_host:
    # Both spellings: the Firebase SDKs read one, google-cloud-storage the other.
    os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = settings.firebase_storage_emulator_host
    os.environ["STORAGE_EMULATOR_HOST"] = f"http://{settings.firebase_storage_emulator_host}"

# 3. Only now import the app factory.
from api import create_app  # noqa: E402

app = create_app()


def main() -> None:
    # Never a literal: config/ports.json is the single source of truth and
    # scripts/check-ports.mjs fails the build on a hardcoded port.
    port = int(os.environ.get("PORT") or settings.ports["backend"])
    host = os.environ.get("HOST", "127.0.0.1")
    # FRAME_NO_RELOAD turns the watcher off WITHOUT pretending to be deployed.
    # Setting K_SERVICE to get the same effect would also close the dev auth
    # bypass gate — correct, and exactly wrong for a local demo run, where the
    # symptom is an unexplained 401 that looks like a broken bypass secret.
    reload_enabled = (
        os.environ.get("K_SERVICE") is None
        and os.environ.get("FRAME_NO_RELOAD", "").lower() not in {"1", "true", "yes"}
    )

    if reload_enabled:
        uvicorn.run(
            "api.cloudrun:app",  # reload mode requires an import string
            host=host,
            port=port,
            reload=True,
            # `lib` matters as much as `api`: the permission library, the row
            # writer and the compiler live there, and leaving it unwatched means
            # the dev server serves stale logic while the source says otherwise.
            reload_dirs=["api", "lib", "consumers", "jobs", "migrations"],
            log_level=settings.log_level.lower(),
        )
    else:
        uvicorn.run(
            app,
            # Loopback unless this really is a container. Binding 0.0.0.0 on a
            # laptop because reload happened to be off would put the API on
            # every interface the machine has.
            host="0.0.0.0" if os.environ.get("K_SERVICE") else host,  # noqa: S104
            port=port,
            # Asked for only when importable. uvicorn does NOT fall back when a
            # named loop is missing — it raises ModuleNotFoundError at startup,
            # which on Windows (where uvloop has no wheel) means this branch
            # cannot run at all. The comment here previously claimed the
            # opposite, so the failure looked like a broken environment rather
            # than a wrong argument.
            loop=_fast_loop(),
            http=_fast_http(),
            limit_concurrency=400,
            log_level=settings.log_level.lower(),
        )


def _fast_loop() -> str:
    from importlib.util import find_spec

    return "uvloop" if find_spec("uvloop") is not None else "auto"


def _fast_http() -> str:
    from importlib.util import find_spec

    return "httptools" if find_spec("httptools") is not None else "auto"


if __name__ == "__main__":
    main()
