"""A saved view: user-authored data, never a deployed artifact.

This is the requirement that forced the generic index projection. A view carries
an arbitrary filter and sort *written by a user at runtime*, while Firestore
composite indexes are declared, deployed, and capped per database. A design that
indexed fields would need an index a data write cannot create; indexing generic
slots instead makes the index count O(slots) rather than O(Blueprints × view
shapes).

**A view is not a permission.** Sharing one grants nothing: two people opening
the same saved view from the same URL see the rows and columns their own
Decision allows, which is the whole demonstration Milestone 1 exists to make. A
view that granted access would be a second permission surface, and one users
could author.

**Column selection is presentation, not filtering.** Hiding a column in a view
does not withhold it — the wire response still carries what the reader may see,
and `columnStubs` still names what they may not. Conflating the two would let a
user believe a view protects something it does not.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ViewScope(StrEnum):
    PERSONAL = "personal"
    """Visible only to its author. The default, because a view saved to try
    something out should not appear in a colleague's list."""

    SHARED = "shared"
    """Visible to everyone who can read the Blueprint. Still grants nothing."""

    DEFAULT = "default"
    """The view a register opens on. One per Blueprint; setting a new one is a
    governance action, because it changes what every reader sees first."""


class ViewSort(_Strict):
    field_id: str
    direction: Literal["asc", "desc"] = "asc"


class ViewColumn(_Strict):
    field_id: str
    width: int | None = None
    hidden: bool = False
    """Presentation only. A hidden column is still in the response and still
    exports — see the module docstring."""

    pinned: Literal["left", "right"] | None = None


class SavedView(_Strict):
    id: str
    name: str
    blueprint_id: str
    workspace_id: str
    scope: ViewScope = ViewScope.PERSONAL
    author: str

    filter: dict[str, Any] | None = None
    """A shared-grammar AST, never a string.

    A string filter needs a parser wherever it is read, and a second parser is a
    second grammar — at which point a saved view and a permission rule can
    disagree about what ``status = 'open'`` means, on the same register, with no
    error anywhere.
    """

    sort: list[ViewSort] = Field(default_factory=list)
    columns: list[ViewColumn] = Field(default_factory=list)
    group_by: str | None = None

    row_height: Literal["compact", "normal", "tall"] = "normal"

    blueprint_version: int = 1
    """The version this view was authored against.

    Kept so a field removed by a later version produces "this view refers to a
    field that no longer exists" rather than an empty grid — a view that
    silently returns nothing is indistinguishable from a permission denial, and
    users conclude the wrong one.
    """

    created_at: Any | None = None
    updated_at: Any | None = None

    def sort_tuples(self) -> tuple[tuple[str, str], ...]:
        return tuple((s.field_id, s.direction) for s in self.sort)

    def visible_columns(self) -> tuple[str, ...]:
        return tuple(c.field_id for c in self.columns if not c.hidden)
