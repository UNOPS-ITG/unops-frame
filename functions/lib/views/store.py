"""Reading and writing saved views.

Separate from the row store because views are governed differently: they are
metadata about presentation, they grant nothing, and their retention follows the
Blueprint rather than the rows. They also do not go through the row writer —
BP-4's single write path is about *row* validation, and routing view saves
through it would mean either a fake Blueprint or a special case inside the one
function that must not have special cases.
"""

from __future__ import annotations

from typing import Any

from lib.views.model import SavedView, ViewScope

VIEWS = "views"


def _collection(db: Any, workspace_id: str, blueprint_id: str) -> Any:
    from lib.paths import BLUEPRINTS, workspace

    return (
        workspace(db, workspace_id)
        .collection(BLUEPRINTS)
        .document(blueprint_id)
        .collection(VIEWS)
    )


def list_views(db: Any, workspace_id: str, blueprint_id: str, author: str) -> list[SavedView]:
    """Every view this principal may see: their own, plus shared and default.

    Personal views of *other* people are excluded here rather than trimmed
    later. A personal view's name is written casually — "mine, broken", "for the
    Tuesday call" — and was never meant to be read by a colleague.
    """
    out: list[SavedView] = []
    for snapshot in _collection(db, workspace_id, blueprint_id).stream():
        data = snapshot.to_dict() or {}
        data.setdefault("id", snapshot.id)
        view = SavedView.model_validate(data)
        if view.scope is ViewScope.PERSONAL and view.author != author:
            continue
        out.append(view)
    return sorted(out, key=lambda v: (v.scope is not ViewScope.DEFAULT, v.name.lower()))


def get_view(db: Any, workspace_id: str, blueprint_id: str, view_id: str) -> SavedView | None:
    snapshot = _collection(db, workspace_id, blueprint_id).document(view_id).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    data.setdefault("id", view_id)
    return SavedView.model_validate(data)


def save_view(db: Any, view: SavedView) -> None:
    _collection(db, view.workspace_id, view.blueprint_id).document(view.id).set(
        view.model_dump(mode="json")
    )


def delete_view(db: Any, workspace_id: str, blueprint_id: str, view_id: str) -> None:
    _collection(db, workspace_id, blueprint_id).document(view_id).delete()


def clear_default(db: Any, workspace_id: str, blueprint_id: str, except_id: str) -> None:
    """Demote whatever was the default.

    Enforced by rewriting rather than by a uniqueness constraint the store does
    not have. Two defaults would make which one a register opens on depend on
    document ordering — stable enough to look correct in testing and different
    in production.
    """
    for view in list_views(db, workspace_id, blueprint_id, author="*"):
        if view.scope is ViewScope.DEFAULT and view.id != except_id:
            demoted = view.model_copy(update={"scope": ViewScope.SHARED})
            save_view(db, demoted)
