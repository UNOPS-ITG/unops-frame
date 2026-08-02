"""Firestore clients.

Two singletons, two rules.

**The named database is not optional.** Frame's data lives in a database called
``frame``, never ``(default)``. Both constructors are passed it explicitly. A
client built without it reads an empty store and reports success — no error, no
data, and a developer who reasonably concludes the write path is broken.

**The async client binds to the event loop it was first constructed on.** Inside
uvicorn that loop lives for the life of the process and the singleton is
correct. Anywhere that bridges into async per call — a Pub/Sub pull loop, a
task worker, a CLI using ``asyncio.run()`` — the loop is destroyed when the call
returns, the singleton survives in the warm process, and the *next* invocation
fails with ``Event loop is closed``. The signature of that bug is "cold starts
always work, retries always fail", and it is expensive to find.

  * ASGI request handlers ............ ``get_async_db()``
  * anything outside the ASGI process  ``get_db()``, or call ``reset_async_db()``
    before each ``asyncio.run()``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

_sync_db: Any | None = None
_sync_db_lock = threading.Lock()

_async_db: Any | None = None
_async_db_lock = threading.Lock()



def get_db() -> Any:
    """The synchronous client. Safe on any thread, any loop, or no loop."""
    global _sync_db
    if _sync_db is None:
        with _sync_db_lock:
            if _sync_db is None:  # double-checked: a cold burst builds exactly one
                from google.cloud.firestore import Client

                from api.core.config import get_settings

                settings = get_settings()
                _sync_db = Client(
                    project=settings.gcp_project_id,
                    database=settings.firestore_database_id,
                )
    return _sync_db


def get_async_db() -> Any:
    """The asynchronous client. Only from code on a persistent event loop."""
    global _async_db
    if _async_db is None:
        with _async_db_lock:
            if _async_db is None:
                from google.cloud.firestore import AsyncClient

                from api.core.config import get_settings

                settings = get_settings()
                _async_db = AsyncClient(
                    project=settings.gcp_project_id,
                    database=settings.firestore_database_id,
                )
    return _async_db


def reset_async_db() -> None:
    """Drop the cached AsyncClient.

    A worker that bridges into async via ``asyncio.run()`` must call this before
    each run. Never call it from FastAPI code, where the singleton is shared
    across requests on one long-lived loop and dropping it mid-flight would
    strand in-progress work.
    """
    global _async_db
    with _async_db_lock:
        _async_db = None


def run_in_transaction[T](body: Callable[[Any], T]) -> T:
    """Run ``body`` inside a Firestore transaction — or directly, under a fake.

    The isinstance check is a test seam. With the real client the body is
    wrapped by Firestore's transactional decorator and may be **retried** on
    contention, so it must be free of side effects other than writes on the
    transaction object. Under a fake the transaction is not a real
    ``Transaction``, the check fails, and the body runs directly — which makes
    the exact read/guard/write sequence unit-testable with no emulator and no
    network. Frame's single row-write path is why that matters.
    """
    from google.cloud.firestore import transactional
    from google.cloud.firestore_v1.transaction import Transaction as _RealTransaction

    txn = get_db().transaction()
    if isinstance(txn, _RealTransaction):
        return transactional(body)(txn)  # type: ignore[no-any-return]
    return body(txn)
