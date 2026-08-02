"""What a subscriber is told changed.

Every test here is a disclosure question, not a delivery question. A delta is a
statement that a row exists and moved, and the register's permission rules exist
precisely to control who may learn that.
"""

from __future__ import annotations

from typing import Any

from lib.permissions.evaluate import compile_rules
from lib.permissions.model import Principal
from lib.rows.deltas import DeltaKind, Room, authorise_deltas, may_subscribe
from tests.unit.test_read_page import _bp_with, _gte, _lt

MAYA = Principal(subject="u1", email="maya@unops.org", groups=frozenset({"staff"}))
ALLOW_ALL = [{"principals": ["*"], "actions": ["read"], "effect": "allow"}]


def _row(row_id: str, amount: int = 1) -> dict[str, Any]:
    return {
        "id": row_id,
        "values": {"title": "A risk", "amount": amount, "owner_rationale": "sealed"},
    }


def _event(row_id: str, *, changed: list[str], type_: str = "frame.row.updated") -> dict[str, Any]:
    return {
        "type": type_,
        "rowId": row_id,
        "changedFields": changed,
        "workspaceId": "ws1",
        "blueprintId": "risk",
    }


def _authorise(
    events: list[dict[str, Any]],
    rows: dict[str, dict[str, Any] | None],
    rules: list[dict[str, Any]],
    **kw: Any,
) -> list[Any]:
    compiled = _bp_with(rules)
    return authorise_deltas(events, rows, compiled, compile_rules(compiled), MAYA, **kw)


# --- a delta discloses existence -----------------------------------------


def test_a_row_the_subscriber_cannot_read_produces_no_delta() -> None:
    """"Row r5 changed" tells the reader r5 exists — which on a register whose
    row set is itself sensitive is the disclosure the rules were written to
    prevent."""
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _gte("amount", 100)}
    ]
    deltas = _authorise([_event("r1", changed=["title"])], {"r1": _row("r1", 500)}, rules)

    assert deltas == []


def test_a_row_that_becomes_invisible_is_removed_only_if_it_was_sent() -> None:
    """Both halves matter. A client still rendering the row needs it gone; a
    client that never had it must not learn it exists."""
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _gte("amount", 100)}
    ]
    event, rows = [_event("r1", changed=["amount"])], {"r1": _row("r1", 500)}

    known = _authorise(event, rows, rules, known_to_client=frozenset({"r1"}))
    unknown = _authorise(event, rows, rules)

    assert [(d.kind, d.row_id) for d in known] == [(DeltaKind.REMOVE, "r1")]
    assert unknown == []


def test_a_removal_carries_no_reason() -> None:
    """"You may no longer see this" and "this was deleted" are deliberately
    indistinguishable — telling them apart is itself a disclosure."""
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _gte("amount", 100)}
    ]
    scoped_out = _authorise(
        [_event("r1", changed=["amount"])], {"r1": _row("r1", 500)}, rules,
        known_to_client=frozenset({"r1"}),
    )
    deleted = _authorise(
        [_event("r2", changed=[], type_="frame.row.deleted")], {"r2": None}, ALLOW_ALL,
        known_to_client=frozenset({"r2"}),
    )

    assert scoped_out[0].to_payload() == {"kind": "remove", "rowId": "r1", "changedFields": []}
    assert deleted[0].to_payload() == {"kind": "remove", "rowId": "r2", "changedFields": []}


def test_a_change_to_only_restricted_fields_is_silence_not_an_empty_upsert() -> None:
    """An upsert with an empty field list still leaks that a restricted field
    moved — which is exactly what PM-10 audits a read of."""
    rules = [{"principals": ["*"], "actions": ["read"], "effect": "allow", "max_band": 0}]
    deltas = _authorise(
        [_event("r1", changed=["owner_rationale"])], {"r1": _row("r1")}, rules,
        known_to_client=frozenset({"r1"}),
    )

    assert deltas == []


def test_changed_fields_are_trimmed_to_what_the_reader_may_read() -> None:
    """A field id the reader cannot see is itself a hint about the row."""
    rules = [{"principals": ["*"], "actions": ["read"], "effect": "allow", "max_band": 0}]
    deltas = _authorise(
        [_event("r1", changed=["title", "owner_rationale"])], {"r1": _row("r1")}, rules,
    )

    assert deltas[0].changed_fields == ("title",)


# --- evaluated against current state, not against the event --------------


def test_the_decision_uses_the_row_as_it_stands_not_as_the_event_described_it() -> None:
    """An event is a statement about a moment that has passed. By delivery the
    row may have moved again, and trusting the event would announce a row that
    has since become private."""
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _gte("amount", 100)}
    ]
    # The event says a harmless field changed; the row has since moved out of scope.
    deltas = _authorise(
        [_event("r1", changed=["title"])], {"r1": _row("r1", 900)}, rules,
        known_to_client=frozenset({"r1"}),
    )

    assert deltas[0].kind is DeltaKind.REMOVE


def test_a_row_that_becomes_visible_arrives_as_an_upsert() -> None:
    """The client has never seen it, so there is nothing to patch — it fetches."""
    deltas = _authorise([_event("r1", changed=["amount"])], {"r1": _row("r1")}, ALLOW_ALL)
    assert deltas[0].kind is DeltaKind.UPSERT


def test_a_vanished_row_removes_even_without_a_delete_event() -> None:
    """A missing row and a delete event mean the same thing to a subscriber, and
    relying on the event alone loses the row when the event is compacted away."""
    deltas = _authorise(
        [_event("r1", changed=["title"])], {"r1": None}, ALLOW_ALL,
        known_to_client=frozenset({"r1"}),
    )
    assert deltas[0].kind is DeltaKind.REMOVE


# --- the batch -----------------------------------------------------------


def test_one_delta_per_row_per_batch() -> None:
    """Three upserts for one row is three refetches for one answer."""
    events = [
        _event("r1", changed=["title"]),
        _event("r1", changed=["amount"]),
        _event("r2", changed=["title"]),
    ]
    deltas = _authorise(events, {"r1": _row("r1"), "r2": _row("r2")}, ALLOW_ALL)

    assert [d.row_id for d in deltas] == ["r1", "r2"]


def test_a_delta_never_carries_values() -> None:
    """The event stream would otherwise be a second read path — one trimmed for
    whoever wrote the row rather than for whoever is subscribed."""
    deltas = _authorise([_event("r1", changed=["title"])], {"r1": _row("r1")}, ALLOW_ALL)
    payload = deltas[0].to_payload()

    assert set(payload) == {"kind", "rowId", "changedFields"}
    assert "values" not in payload


# --- the room ------------------------------------------------------------


def test_a_room_is_keyed_on_the_blueprint_version() -> None:
    """A rule change produces a new version. A subscription that outlived the
    rules it was granted under would make PM-4's 60-second propagation budget
    unmeetable."""
    assert Room("ws1", "risk", 3).key == "ws1/risk/v3"
    assert Room("ws1", "risk", 4).key != Room("ws1", "risk", 3).key


def test_a_room_ignores_events_from_another_blueprint() -> None:
    room = Room("ws1", "risk", 1)
    assert room.accepts(_event("r1", changed=[])) is True
    assert room.accepts({**_event("r1", changed=[]), "blueprintId": "other"}) is False
    assert room.accepts({**_event("r1", changed=[]), "workspaceId": "ws2"}) is False


def test_a_principal_with_no_read_grant_cannot_open_a_room() -> None:
    """Someone with no possible read should not hold an open connection, even
    one that would emit nothing."""
    compiled = _bp_with([{"principals": ["someone-else"], "actions": ["read"], "effect": "allow"}])
    assert may_subscribe(compiled, compile_rules(compiled), MAYA) is False


def test_a_conditional_grant_still_opens_a_room() -> None:
    """The gate is cheap and in front of per-row evaluation, not a replacement
    for it. A rule whose condition does not match an empty row must not close
    the door — the register may still hold rows this principal can see."""
    rules = [
        {"principals": ["*"], "actions": ["read"], "effect": "allow",
         "row_condition": _lt("amount", 100)}
    ]
    compiled = _bp_with(rules)
    assert may_subscribe(compiled, compile_rules(compiled), MAYA) is True
