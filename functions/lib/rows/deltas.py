"""The delta channel: what a client is told changed.

**No client store listener on row data, ever.** A Firestore listener attached in
the browser evaluates Firestore rules, not Frame's permission library — so
real-time would become a second, weaker decision site, and the one that is
hardest to audit because it runs on someone else's machine. Real-time is
server-mediated through rooms whose subscription is itself an evaluated
permission decision.

**A delta discloses existence.** "Row r5 changed" tells the reader that r5
exists, which on a register whose row set is itself sensitive is the disclosure
the permission rules were written to prevent. So every event is evaluated
against the current row before it is emitted, exactly as a read would be — the
event stream is a *consumer* of the permission library, not a bypass with a
subscription.

**Three delta kinds, and the third is the one people forget.** A row that
becomes visible is an ``upsert``; a row that changes while visible is an
``upsert``; and a row that *stops* being visible — because it was deleted, or
because its values moved it out of the reader's scope, or because a rule
changed — is a ``remove``. Without ``remove``, a grid keeps rendering a row the
reader may no longer see, and no amount of correctness on the read path fixes
it.

``remove`` carries no reason. "You may no longer see this" and "this was
deleted" are deliberately indistinguishable to the client, because telling them
apart is itself a disclosure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from lib.permissions.evaluate import CompiledRuleSet, evaluate_row
from lib.permissions.model import Principal
from lib.rows.outbox import EventType

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint


class DeltaKind(StrEnum):
    UPSERT = "upsert"
    REMOVE = "remove"


_REMOVAL_EVENTS = {EventType.ROW_DELETED, EventType.CHILD_DELETED}


@dataclass(frozen=True, slots=True)
class Delta:
    """What crosses the wire. Identifiers only.

    ``changed_fields`` names fields, never values, and is further trimmed to
    what this reader may read — a field id the reader cannot see is itself a
    hint about what the row contains.
    """

    kind: DeltaKind
    row_id: str
    changed_fields: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "rowId": self.row_id,
            "changedFields": list(self.changed_fields),
        }


def authorise_deltas(
    events: list[dict[str, Any]],
    rows: dict[str, dict[str, Any] | None],
    compiled: CompiledBlueprint,
    rule_set: CompiledRuleSet,
    principal: Principal,
    *,
    known_to_client: frozenset[str] = frozenset(),
) -> list[Delta]:
    """Turn raw outbox events into the deltas this principal may receive.

    ``rows`` is the CURRENT state of each affected row, fetched by the caller —
    ``None`` for one that no longer exists. Evaluating against current state
    rather than against the event is deliberate: an event is a statement about a
    moment that has passed, and by the time it is delivered the row may have
    moved again. Trusting the event would let a row that has since become
    private be announced.

    ``known_to_client`` is what this subscriber already has on screen. It is
    what makes the difference between silence and a ``remove``: a row that turns
    invisible and was never sent needs no delta at all, and sending one would
    disclose that something the reader cannot see changed.
    """
    deltas: list[Delta] = []
    seen: set[str] = set()

    for event in events:
        row_id = event.get("rowId")
        if not isinstance(row_id, str) or row_id in seen:
            # One delta per row per batch. A client that receives three upserts
            # for one row does three refetches for one answer.
            continue
        seen.add(row_id)

        row = rows.get(row_id)
        event_type = event.get("type")

        if row is None or event_type in {e.value for e in _REMOVAL_EVENTS}:
            if row_id in known_to_client:
                deltas.append(Delta(DeltaKind.REMOVE, row_id))
            continue

        decision = evaluate_row(rule_set, principal, row, compiled=compiled)
        if not decision.visible:
            # Withheld now. A remove only if this subscriber was told about it
            # before — otherwise the delta itself is the disclosure.
            if row_id in known_to_client:
                deltas.append(Delta(DeltaKind.REMOVE, row_id))
            continue

        changed = tuple(
            field_id
            for field_id in event.get("changedFields", ())
            if field_id in decision.readable_fields
        )
        if not changed and row_id in known_to_client:
            # Everything that changed is invisible to this reader. Saying "this
            # row changed" with an empty field list still leaks that a
            # restricted field moved — which is precisely what PM-10 audits a
            # read of. Silence is the correct answer.
            continue

        deltas.append(Delta(DeltaKind.UPSERT, row_id, changed))

    return deltas


@dataclass(frozen=True, slots=True)
class Room:
    """A subscription. Membership IS an evaluated permission decision.

    Keyed on the Blueprint version as well as its id: a rule change produces a
    new version, and subscribers to the old one are re-evaluated rather than
    grandfathered. PM-4's 60-second propagation budget is only meetable if a
    subscription cannot outlive the rules it was granted under.
    """

    workspace_id: str
    blueprint_id: str
    blueprint_version: int

    @property
    def key(self) -> str:
        return f"{self.workspace_id}/{self.blueprint_id}/v{self.blueprint_version}"

    def accepts(self, event: dict[str, Any]) -> bool:
        return (
            event.get("workspaceId") == self.workspace_id
            and event.get("blueprintId") == self.blueprint_id
        )


def may_subscribe(
    compiled: CompiledBlueprint, rule_set: CompiledRuleSet, principal: Principal
) -> bool:
    """Whether this principal may open a room at all.

    Someone with no possible read on the register should not hold an open
    connection to it, even one that would emit nothing. Per-row evaluation still
    happens on every delta — this is a cheap gate in front of it.
    """
    from lib.permissions.evaluate import may_at_blueprint_level
    from lib.permissions.model import Action

    del compiled  # the gate is rule-level; per-row evaluation uses the Blueprint
    return may_at_blueprint_level(rule_set, principal, Action.READ)
