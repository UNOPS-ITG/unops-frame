"""The row wire contract.

One shape for every Blueprint that will ever exist — which is what "generated
from metadata" means in practice. There is no per-Blueprint response model,
because the moment there is one, generating it is a code-generation step with a
build, and Frame's whole claim is that publishing a Blueprint takes effect
immediately.

Three things are present from the first response and would be a breaking change
to add later:

* ``annotation``, with the ``exact | estimated`` discriminator. An exact
  view-level total means evaluating every row in the filtered set, which
  collides with the windowed 50,000-row requirement. The discriminator lets the
  server be honest about which it gave without changing the schema.
* ``columnStubs`` — the fields withheld on *every* row of the page, which the
  grid renders as a restricted column rather than a grid of restricted cells.
* ``plan`` — why the page cost what it did. A view that cannot be served by the
  index should be able to say so; "loading…" forever is not a diagnosis.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.base import RequestSchema, ResponseSchema


class AnnotationOut(ResponseSchema):
    """PM-5 transparency as a machine-readable object, never an English string.

    The index requires string externalisation from day one across six locales,
    and a server-rendered sentence cannot be translated at the client.
    """

    visible: int
    withheld: int
    total: int
    scope: str = "page"
    certainty: Literal["exact", "estimated"] = "exact"
    ceiling: int | None = None


class PagePlanOut(ResponseSchema):
    store_filters: int = 0
    post_filtered: bool = False
    scanned: int = 0
    rounds: int = 0
    scan_budget_exhausted: bool = False
    reasons: list[str] = Field(default_factory=list)
    unsortable: str | None = None


class RowOut(ResponseSchema):
    """One row. ``values`` passes through untouched — see ``schemas.base``."""

    id: str
    values: dict[str, Any]
    field_versions: dict[str, int] = Field(default_factory=dict)
    lifecycle_status: str = "draft"
    updated_at: Any | None = None
    updated_by: str | None = None


class RowPageOut(ResponseSchema):
    rows: list[RowOut]
    annotation: AnnotationOut
    cursor: str | None = None
    has_more: bool = False
    column_stubs: list[str] = Field(default_factory=list)
    plan: PagePlanOut
    blueprint_id: str
    blueprint_version: int


class SortIn(RequestSchema):
    field_id: str
    direction: Literal["asc", "desc"] = "asc"


class QueryIn(RequestSchema):
    """A query. ``filter`` is a shared-grammar AST, never a string.

    A string filter would need a parser on the wire, and a parser on the wire is
    a second grammar that drifts from the one the permission evaluator uses —
    at which point a filter and a permission rule can disagree about what
    ``status = 'open'`` means.
    """

    filter: dict[str, Any] | None = None
    sort: list[SortIn] = Field(default_factory=list)
    limit: int = 100
    cursor: str | None = None


class RowWriteIn(RequestSchema):
    """A field-scoped write.

    ``values`` carries only the fields being changed — not the whole row. A
    whole-row save cannot express last-write-wins per cell (GR-8), so two people
    editing different cells of one row would lose an edit.

    ``field_versions`` is what the client believes it read. Omitting it means
    "I am not claiming to know the current state", which is how an import or an
    automation writes.
    """

    values: dict[str, Any]
    field_versions: dict[str, int] | None = None


class RowWriteOut(ResponseSchema):
    id: str
    created: bool
    changed_fields: list[str]
    field_versions: dict[str, int]
    values: dict[str, Any]


class ConflictOut(ResponseSchema):
    """A 412 body naming what was lost and what won.

    An error that only says "conflict" forces the client to refetch and guess;
    this one lets it show the user both values and offer to reapply.
    """

    detail: str = "A concurrent edit changed the same fields"
    fields: list[str]
    current: dict[str, Any]
