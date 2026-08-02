"""The Firestore implementation of ``RowSource``.

Separate from ``reader.py`` so the paging rules — over-fetch, the scan bound,
the cursor-of-last-fetched rule — are tested against a fake and the store
translation is tested against the emulator. They fail for different reasons and
mixing them means neither is tested properly.

Reads only. Row writes live in ``writer.py`` and the architectural fitness suite
enforces that; this module holds no write verb.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lib.grammar.compile_query import QueryPlan

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint


class FirestoreRowSource:
    def __init__(self, db: Any, workspace_id: str, compiled: CompiledBlueprint) -> None:
        self._db = db
        self._workspace_id = workspace_id
        self._compiled = compiled

    def fetch(
        self,
        plan: QueryPlan,
        *,
        order_by: tuple[str, str] | None,
        after: dict[str, Any] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        from lib.paths import rows as rows_path

        query: Any = rows_path(self._db, self._workspace_id, self._compiled.id)

        for f in plan.filters:
            query = query.where(f.path, f.op, f.value)

        if order_by is not None:
            field, direction = order_by
            query = query.order_by(field, direction=direction)
            if field != "__name__":
                # A secondary order on the document id, always. Without it two
                # rows sharing a slot value have no defined order between them,
                # and a cursor landing on that boundary either repeats a row or
                # skips one — intermittently, under concurrent writes, which is
                # the hardest kind of pagination bug to reproduce.
                query = query.order_by("__name__", direction=direction)

        if after is not None:
            query = query.start_after(_cursor_document(after, order_by))

        return [_with_id(doc) for doc in query.limit(limit).stream()]


def _cursor_document(
    after: dict[str, Any], order_by: tuple[str, str] | None
) -> dict[str, Any]:
    """The value tuple Firestore resumes from, in order-by order."""
    if order_by is None or order_by[0] == "__name__":
        return {"__name__": after["id"]}
    return {after.get("slot", order_by[0]): after.get("value"), "__name__": after["id"]}


def _with_id(doc: Any) -> dict[str, Any]:
    data = doc.to_dict() or {}
    data.setdefault("id", doc.id)
    return data
