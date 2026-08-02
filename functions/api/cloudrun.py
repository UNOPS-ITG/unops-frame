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
    reload_enabled = os.environ.get("K_SERVICE") is None

    if reload_enabled:
        uvicorn.run(
            "api.cloudrun:app",  # reload mode requires an import string
            host=host,
            port=port,
            reload=True,
            # `lib` matters as much as `api`: the permission library, the row
            # writer and the compiler live there, and leaving it unwatched means
            # the dev server serves stale logic while the source says otherwise.
            reload_dirs=["api", "lib", "consumers", "migrations"],
            log_level=settings.log_level.lower(),
        )
    else:
        uvicorn.run(
            app,
            host="0.0.0.0",  # noqa: S104 - container ingress
            port=port,
            loop="uvloop",  # not installed on Windows; uvicorn falls back cleanly
            http="httptools",
            limit_concurrency=400,
            log_level=settings.log_level.lower(),
        )


if __name__ == "__main__":
    main()
