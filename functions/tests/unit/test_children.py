"""Master-detail, and PM-3 composition.

Every test here is about the same sentence: effective child access is the
child's own rules AND the parent's access, with the parent ceiling applied last
and unconditionally. "Last" is the load-bearing word, and these are the ways it
goes wrong when it is applied anywhere else.
"""

from __future__ import annotations

from typing import Any

from lib.blueprint.compile import compile_blueprint
from lib.blueprint.model import Blueprint, ChildCollection
from lib.permissions.evaluate import compile_rules
from lib.permissions.model import Action, Decision, Principal
from lib.rows.children import (
    PARENT_SNAPSHOT,
    ChildContext,
    child_document,
    compose,
    parent_snapshot,
    read_children,
    restamp_needed,
)
from tests.unit.test_read_page import _gte, _lt

MAYA = Principal(subject="u1", email="maya@unops.org", groups=frozenset({"staff"}))

LINE_ITEM = Blueprint.model_validate({
    "id": "line_item",
    "name": "Line items",
    "workspace_id": "ws1",
    "tier": "team",
    "view_defaults": {"title_field": "description"},
    "fields": [
        {"id": "description", "label": "Description", "type": "text", "variant": "single",
         "required": True, "indexed": True},
        {"id": "amount", "label": "Amount", "type": "number", "variant": "decimal",
         "indexed": True},
        {"id": "sequence", "label": "Sequence", "type": "number", "variant": "integer"},
    ],
    "permissions": [
        {"principals": ["*"], "actions": ["read", "create", "update"], "effect": "allow"},
    ],
})
CHILD = compile_blueprint(LINE_ITEM)
CHILD_RULES = compile_rules(CHILD)

CONTRACT = Blueprint.model_validate({
    "id": "contract",
    "name": "Contracts",
    "workspace_id": "ws1",
    "tier": "team",
    "view_defaults": {"title_field": "title"},
    "fields": [
        {"id": "title", "label": "Title", "type": "text", "variant": "single",
         "required": True, "indexed": True},
        {"id": "classification", "label": "Classification", "type": "single_select",
         "indexed": True,
         "options": [{"key": "open", "label": "Open"}, {"key": "sealed", "label": "Sealed"}]},
        {"id": "value", "label": "Value", "type": "number", "variant": "decimal",
         "indexed": True},
    ],
    "permissions": [
        {"principals": ["*"], "actions": ["read"], "effect": "allow",
         "row_condition": _lt("value", 1_000_000)},
    ],
})
PARENT = compile_blueprint(CONTRACT)

COLLECTION = ChildCollection(id="items", label="Line items", blueprint="line_item")

VISIBLE_PARENT = Decision(
    allowed=frozenset({Action.READ, Action.UPDATE}),
    readable_fields=frozenset(PARENT.fields),
    writable_fields=frozenset(PARENT.fields),
)
INVISIBLE_PARENT = Decision()


def _child(child_id: str, amount: int = 10, sequence: int | None = None) -> dict[str, Any]:
    values: dict[str, Any] = {"description": f"Item {child_id}", "amount": amount}
    if sequence is not None:
        values["sequence"] = sequence
    return {"id": child_id, "values": values}


def _context(parent_decision: Decision, collection: ChildCollection = COLLECTION) -> ChildContext:
    return ChildContext(
        collection=collection,
        parent_row={"id": "c1", "values": {"title": "A contract", "value": 500}},
        parent_decision=parent_decision,
    )


# --- the ceiling ----------------------------------------------------------


def test_a_child_of_an_invisible_parent_is_invisible() -> None:
    """Whatever the child's own rules say. A line item grant that could outrank
    its contract would disclose the contract's existence through a path nobody
    audits — the person reviewing the contract's rules never looks at the line
    item's."""
    decision = compose(CHILD_RULES, CHILD, MAYA, _child("i1"), _context(INVISIBLE_PARENT))
    assert decision.visible is False
    assert decision.allowed == frozenset()


def test_a_child_of_an_invisible_parent_is_absent_not_counted() -> None:
    """Not 403, and not "3 rows withheld" either. A count confirms the parent
    exists, which is the disclosure the ceiling exists to prevent."""
    rows, annotation, stubs = read_children(
        CHILD_RULES, CHILD, MAYA, [_child("i1"), _child("i2")], _context(INVISIBLE_PARENT)
    )

    assert rows == []
    assert annotation.withheld == 0
    assert annotation.visible == 0
    assert stubs == frozenset()


def test_the_child_cannot_exceed_the_parents_actions() -> None:
    """The parent's Decision is an upper bound, not one input among several."""
    read_only_parent = Decision(
        allowed=frozenset({Action.READ}), readable_fields=frozenset(PARENT.fields)
    )
    decision = compose(CHILD_RULES, CHILD, MAYA, _child("i1"), _context(read_only_parent))

    assert Action.READ in decision.allowed
    # The child's own rules grant update and create; the ceiling removes them.
    assert Action.UPDATE not in decision.allowed
    assert Action.CREATE not in decision.allowed


def test_a_visible_parent_lets_the_childs_own_rules_decide() -> None:
    """The ceiling bounds; it does not grant. A permissive parent must not widen
    a restrictive child."""
    restrictive = compile_blueprint(
        Blueprint.model_validate({
            **LINE_ITEM.model_dump(),
            "permissions": [
                {"principals": ["*"], "actions": ["read"], "effect": "allow",
                 "row_condition": _lt("amount", 100)},
            ],
        })
    )
    rules = compile_rules(restrictive)

    small = compose(rules, restrictive, MAYA, _child("i1", amount=10), _context(VISIBLE_PARENT))
    large = compose(rules, restrictive, MAYA, _child("i2", amount=900), _context(VISIBLE_PARENT))

    assert small.visible is True
    assert large.visible is False


def test_a_deny_on_the_child_still_beats_a_visible_parent() -> None:
    denied = compile_blueprint(
        Blueprint.model_validate({
            **LINE_ITEM.model_dump(),
            "permissions": [
                {"principals": ["*"], "actions": ["read"], "effect": "allow"},
                {"principals": ["*"], "actions": ["read"], "effect": "deny",
                 "row_condition": _gte("amount", 100)},
            ],
        })
    )
    rules = compile_rules(denied)
    decision = compose(rules, denied, MAYA, _child("i1", amount=500), _context(VISIBLE_PARENT))
    assert decision.visible is False


# --- the page contract ----------------------------------------------------


def test_children_render_through_the_same_contract_as_a_top_level_page() -> None:
    """A second contract for embedded grids is how a restricted stub comes to
    render as blank in one place and as a stub in another."""
    rows, annotation, _ = read_children(
        CHILD_RULES, CHILD, MAYA, [_child("i1"), _child("i2")], _context(VISIBLE_PARENT)
    )

    assert annotation.visible == 2
    assert annotation.scope == "children"
    assert all("values" in row for row in rows)


def test_children_come_back_in_their_declared_order() -> None:
    """Line items are a sequence a human curated. Store order means the same
    invoice reads differently on two loads."""
    ordered = ChildCollection(
        id="items", label="Line items", blueprint="line_item", ordering_field="sequence"
    )
    rows, _, _ = read_children(
        CHILD_RULES, CHILD, MAYA,
        [_child("c", sequence=3), _child("a", sequence=1), _child("b", sequence=2)],
        _context(VISIBLE_PARENT, ordered),
    )

    assert [r["id"] for r in rows] == ["a", "b", "c"]


def test_an_unordered_item_sorts_last_not_first() -> None:
    """An item appended to a curated list belongs at the end."""
    ordered = ChildCollection(
        id="items", label="Line items", blueprint="line_item", ordering_field="sequence"
    )
    rows, _, _ = read_children(
        CHILD_RULES, CHILD, MAYA,
        [_child("no-seq"), _child("a", sequence=1)],
        _context(VISIBLE_PARENT, ordered),
    )

    assert [r["id"] for r in rows] == ["a", "no-seq"]


def test_ordering_ties_break_on_the_document_id() -> None:
    ordered = ChildCollection(
        id="items", label="Line items", blueprint="line_item", ordering_field="sequence"
    )
    rows, _, _ = read_children(
        CHILD_RULES, CHILD, MAYA,
        [_child("z", sequence=1), _child("a", sequence=1)],
        _context(VISIBLE_PARENT, ordered),
    )
    assert [r["id"] for r in rows] == ["a", "z"]


# --- the denormalised parent copy -----------------------------------------


def test_the_snapshot_carries_exactly_the_rule_referenced_fields() -> None:
    """Bounded on purpose. Copying the whole parent would put fields the child's
    reader may not see onto a document they can fetch."""
    snapshot = parent_snapshot(
        PARENT, {"title": "A contract", "classification": "sealed", "value": 500}
    )

    assert set(snapshot) == {"value"}
    assert "classification" not in snapshot


def test_the_snapshot_is_stored_separately_from_the_childs_own_values() -> None:
    """Merging would let a parent field collide with a child field of the same
    id, and the loser would be silently overwritten — which for a
    rule-referenced field is a permission change nobody made."""
    document = child_document(
        "i1", "items", {"description": "x", "value": 99}, {"value": 500},
        workspace_id="ws1", blueprint_id="line_item", parent_row_id="c1",
    )

    assert document["values"]["value"] == 99
    assert document[PARENT_SNAPSHOT]["value"] == 500


def test_the_collection_id_is_a_field_not_a_collection_name() -> None:
    """One collection-group index set covers every Blueprint that will ever
    exist. A collection per named child collection would multiply index
    definitions per Blueprint against a hard per-database cap."""
    document = child_document(
        "i1", "items", {}, {}, workspace_id="ws1", blueprint_id="line_item", parent_row_id="c1"
    )
    assert document["collectionId"] == "items"


def test_a_restamp_is_needed_only_when_a_rule_referenced_field_changes() -> None:
    """Re-stamping on every parent write turns a one-field edit into a fan-out
    across two hundred children; never re-stamping leaves a stale copy, and a
    stale rule-referenced value is a decision made on facts that are no longer
    true."""
    assert restamp_needed(PARENT, ("value",)) is True
    assert restamp_needed(PARENT, ("title",)) is False
    assert restamp_needed(PARENT, ("title", "value")) is True
    assert restamp_needed(PARENT, ()) is False
