"""Principals, actions and the Decision.

The important shape here is that **a Decision is data, not a boolean**. A
predicate answering yes/no forces every caller to ask a separate question per
field, which is both slow and — more importantly — a place where one caller
forgets to ask. Returning the whole answer at once means the trimmer, the
annotator and the audit writer all consume the same object, and PM-5's
transparency annotations are produced by the evaluator rather than assembled by
whoever remembered.

``masked`` is present and always ``False`` until PM-6 ships. Reserving the field
costs nothing now; adding it later would change the signature every consumer
depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import StrEnum


class Action(StrEnum):
    READ = "read"
    SELECT = "select"
    """Reference a row from a picker or a reference-path formula WITHOUT reading
    the register. Without this verb every Blueprint anyone picks from must be
    readable by everyone who picks, and teams grow duplicate unrestricted
    "picker" Blueprints to route around it."""

    CREATE = "create"
    IMPORT = "import"
    """Distinct from create because bulk creation bypasses the per-row attention
    create assumes."""

    UPDATE = "update"
    DELETE = "delete"
    CHANGE_STATE = "change_state"
    EXPORT = "export"
    PUBLISH = "publish"
    """Create or modify an externally reachable surface. The verb PM-13 audits,
    which is what makes the exposure register complete by construction."""

    MANAGE = "manage"


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is asking. Resolution happens outside this library.

    Keyed on the stable subject rather than the email: an address is mutable and
    reassignable, so keying on it means a renamed or recycled address silently
    inherits or loses grants, and PM-11 access review stops being sound.
    """

    subject: str
    email: str | None = None
    groups: frozenset[str] = frozenset()
    workspace_roles: frozenset[str] = frozenset()
    blueprint_roles: frozenset[str] = frozenset()
    is_service: bool = False

    allow_lists: dict[str, frozenset[str]] = dc_field(default_factory=dict)
    """PM-2a. field id -> the values this principal is scoped to.

    Materialised per principal rather than expressed as a condition, which is
    what makes it *always* push-downable — and therefore affordable at grid
    scale where a general attribute expression is not.
    """

    def identifiers(self) -> frozenset[str]:
        """Everything a rule's principal list can match against."""
        out = {f"user:{self.subject}"}
        if self.email:
            out.add(f"user:{self.email}")
        out |= {f"group:{g}" for g in self.groups}
        out |= {f"role:{r}" for r in self.workspace_roles}
        out |= {f"blueprint_role:{r}" for r in self.blueprint_roles}
        out.add("*")
        return frozenset(out)


@dataclass(frozen=True, slots=True)
class Decision:
    """The complete answer for one principal against one row.

    Never a boolean. See the module docstring.
    """

    allowed: frozenset[Action] = frozenset()
    readable_fields: frozenset[str] = frozenset()
    writable_fields: frozenset[str] = frozenset()
    restricted_fields: frozenset[str] = frozenset()
    """Fields that exist and are withheld. Rendered as typed stubs (PM-5), never
    as absent keys — otherwise every renderer has to branch on key existence."""

    masked: bool = False
    """PM-6 existence masking. Reserved; always False until P2."""

    deciding_rule: str | None = None
    """The most specific matching deny, when access was refused. Recorded in
    audit and surfaced through PM-5a's explanation — generated as a by-product
    of the decision rather than by a second component reasoning about rules."""

    def may(self, action: Action) -> bool:
        return action in self.allowed

    @property
    def visible(self) -> bool:
        """Whether this row appears at all. A row the principal cannot read is
        absent from the row array and represented only in the count pair."""
        return Action.READ in self.allowed


@dataclass(frozen=True, slots=True)
class Annotation:
    """PM-5 transparency, as a machine-readable object.

    Never a pre-baked English string: the index requires string externalisation
    from day one and six locales, and a server-rendered sentence cannot be
    translated at the client.
    """

    visible: int
    withheld: int
    scope: str = "page"
    certainty: str = "exact"
    """``exact`` or ``estimated``. An exact view-level total requires evaluating
    every row in the filtered set, which collides with the 50,000-row windowed
    requirement — so the discriminator lives in the wire schema from the first
    response and the ceiling stays a configuration value rather than a refactor."""

    ceiling: int | None = None

    @property
    def total(self) -> int:
        return self.visible + self.withheld
