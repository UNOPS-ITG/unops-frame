"""Blueprints: the metadata every other surface is generated from.

What a client gets here is the **compiled** view, not the stored document — the
resolved field list with its storage kind, its sensitivity band, whether it is
sortable server-side, and the view defaults. A client that read the raw document
would have to re-implement compilation to know whether a column can be sorted,
and that second implementation would drift.

Index plan and slot pressure are exposed on purpose. Running out of sort slots
is a real product constraint a user experiences as "I cannot sort by this
column", and a constraint the UI cannot see is one it explains as a bug.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from api.core.exceptions import NotFoundError
from api.dependencies.auth import CurrentUser
from api.schemas.base import ResponseSchema
from lib.blueprint.compile import CompiledBlueprint
from lib.blueprint.store import BlueprintNotFound, list_blueprints, load_compiled

router = APIRouter(tags=["blueprints"])


def _db(request: Request) -> Any:
    from lib.firestore import get_db

    return get_db()


Db = Annotated[Any, Depends(_db)]


class FieldOut(ResponseSchema):
    id: str
    label: str
    type: str
    variant: str | None = None
    storage: str
    required: bool = False
    read_only: bool = False
    set_once: bool = False
    sensitivity: int = 0
    restricted: bool = False
    """At or above the band threshold. Precomputed here because the grid, the
    export path and the search indexer all ask the same question."""

    indexed: bool = False
    sortable: bool = False
    """Whether the STORE can order by it — not whether the type is orderable.
    Slots are finite, and a client that assumes otherwise renders a sort control
    that silently does nothing."""

    filterable: bool = False
    options: list[dict[str, Any]] | None = None
    default: Any = None
    help_text: str | None = None

    dimension: str | None = None
    """Which corporate dimension a `corporate_reference` field points at
    (PRD 14).

    On the wire because the picker cannot exist without it: a field declared as
    corporate data with no dimension has nothing to search, and the client would
    otherwise have to guess from the field id — which is exactly the kind of
    inference that works until someone names a field sensibly.
    """


class BlueprintOut(ResponseSchema):
    id: str
    name: str
    version: int
    tier: str
    fields: list[FieldOut]
    title_field: str | None = None
    searchable_fields: list[str]
    slot_pressure: dict[str, str]
    unassignable_sorts: list[str]
    """Declared sortable, but no slot was left. Surfaced rather than silently
    dropped: the steward can retire a sort they no longer need."""


@router.get("/workspaces/{workspace_id}/blueprints")
def list_workspace_blueprints(
    workspace_id: str, user: CurrentUser, db: Db
) -> list[BlueprintOut]:
    from lib.blueprint.compile import compile_cached

    return [_out(compile_cached(bp)) for bp in list_blueprints(db, workspace_id)]


@router.get("/workspaces/{workspace_id}/blueprints/{blueprint_id}")
def get_blueprint(
    workspace_id: str, blueprint_id: str, user: CurrentUser, db: Db
) -> BlueprintOut:
    try:
        return _out(load_compiled(db, workspace_id, blueprint_id))
    except BlueprintNotFound as exc:
        raise NotFoundError(f"No Blueprint {blueprint_id!r}") from exc


def _out(compiled: CompiledBlueprint) -> BlueprintOut:
    bp = compiled.blueprint
    return BlueprintOut(
        id=compiled.id,
        name=bp.name,
        version=compiled.version,
        tier=str(bp.tier),
        fields=[
            FieldOut(
                id=fid,
                label=cf.definition.label,
                type=cf.definition.type,
                variant=cf.definition.variant,
                storage=cf.storage,
                required=cf.definition.required,
                read_only=cf.definition.read_only,
                set_once=cf.definition.set_once,
                sensitivity=cf.definition.sensitivity,
                restricted=cf.is_restricted,
                indexed=cf.definition.indexed,
                sortable=cf.sort_slot is not None,
                filterable=cf.eq_token_prefix is not None,
                options=(
                    [o.model_dump(by_alias=True) for o in cf.definition.options]
                    if cf.definition.options
                    else None
                ),
                default=cf.definition.default,
                help_text=cf.definition.help_text,
                dimension=cf.definition.dimension,
            )
            for fid, cf in compiled.fields.items()
        ],
        title_field=compiled.title_field,
        searchable_fields=list(compiled.searchable_fields),
        slot_pressure=compiled.index_plan.slot_pressure,
        unassignable_sorts=list(compiled.index_plan.unassignable),
    )
