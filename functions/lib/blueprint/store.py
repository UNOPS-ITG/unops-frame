"""Loading and compiling a Blueprint from the store.

Blueprints are **user-authored data at every tier**, not application
configuration: a steward publishes one and it takes effect immediately, with no
build and no deploy. That is the whole claim, and it is why this module reads
from Firestore rather than from the repository — the field type registry
(``registry.py``) is the opposite case and correctly lives in the repo.

Compilation is cached by the serialised document rather than by
``(id, version)``. An unversioned edit during development would otherwise serve
a stale compilation, and that bug presents to the author as "my change did
nothing" — the single most expensive kind of feedback to debug.
"""

from __future__ import annotations

from typing import Any

from lib.blueprint.compile import CompiledBlueprint, compile_cached
from lib.blueprint.model import Blueprint


class BlueprintNotFound(LookupError):
    pass


def load_blueprint(db: Any, workspace_id: str, blueprint_id: str) -> Blueprint:
    from lib.paths import blueprint as blueprint_path

    snapshot = blueprint_path(db, workspace_id, blueprint_id).get()
    if not snapshot.exists:
        raise BlueprintNotFound(f"{workspace_id}/{blueprint_id}")

    data = snapshot.to_dict() or {}
    data.setdefault("id", blueprint_id)
    data.setdefault("workspace_id", workspace_id)
    return Blueprint.model_validate(data)


def load_compiled(db: Any, workspace_id: str, blueprint_id: str) -> CompiledBlueprint:
    return compile_cached(load_blueprint(db, workspace_id, blueprint_id))


def list_blueprints(db: Any, workspace_id: str) -> list[Blueprint]:
    from lib.paths import BLUEPRINTS, workspace

    out: list[Blueprint] = []
    for snapshot in workspace(db, workspace_id).collection(BLUEPRINTS).stream():
        data = snapshot.to_dict() or {}
        data.setdefault("id", snapshot.id)
        data.setdefault("workspace_id", workspace_id)
        out.append(Blueprint.model_validate(data))
    return out
