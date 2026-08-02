"""Child rows, and PM-3 composition.

The rule the whole of master-detail rests on:

    effective child access = the child's own rules AND the parent's access,
    with the parent ceiling applied LAST and unconditionally.

"Last" is the load-bearing word. A child grant that could widen access above its
parent would mean a line item discloses the existence of a contract nobody was
meant to know about — and it would do so through a path nobody audits, because
the person reviewing the contract's rules never looks at the line item's.

Three consequences fall out of it:

**A child of an invisible parent is invisible**, whatever its own rules say. Not
403 — absent, because a 403 confirms the parent exists.

**A cross-parent child query is a way to FIND candidates, never a way to skip
evaluation.** ``child_collection_group`` returns children from every parent in
the database; each one still has its parent's Decision applied. A collection
group query that trusted its own filter would be the fastest permission bypass
in the product.

**The child carries a denormalised copy of exactly the parent fields the rules
read.** That is what makes the ceiling computable without fetching every parent,
and it is why ``rule_referenced_fields`` exists on the compiled Blueprint. A
stale copy is a silent permission leak, so it is re-stamped on parent write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lib.permissions.evaluate import CompiledRuleSet, evaluate_row
from lib.permissions.model import Decision, Principal
from lib.permissions.trim import trim_page

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint
    from lib.blueprint.model import ChildCollection

PARENT_SNAPSHOT = "parentValues"
"""Where the denormalised parent fields live on a child document.

A separate key rather than merged into ``values``: merging would let a parent
field collide with a child field of the same id, and the loser would be silently
overwritten — which for a rule-referenced field is a permission change nobody
made.
"""


@dataclass(frozen=True, slots=True)
class ChildContext:
    collection: ChildCollection
    parent_row: dict[str, Any]
    parent_decision: Decision


def compose(
    child_rule_set: CompiledRuleSet,
    child_compiled: CompiledBlueprint,
    principal: Principal,
    child_row: dict[str, Any],
    context: ChildContext,
) -> Decision:
    """The child's Decision, with the parent ceiling applied last.

    Delegates to the one evaluator rather than reimplementing composition —
    ``evaluate_row`` already applies ``parent_decision`` unconditionally at the
    end, which is the only correct order.
    """
    return evaluate_row(
        child_rule_set,
        principal,
        child_row,
        compiled=child_compiled,
        parent_decision=context.parent_decision,
        parent_row=context.parent_row,
    )


def read_children(
    child_rule_set: CompiledRuleSet,
    child_compiled: CompiledBlueprint,
    principal: Principal,
    rows: list[dict[str, Any]],
    context: ChildContext,
) -> tuple[list[dict[str, Any]], Any, frozenset[str]]:
    """Trim a parent's children for one reader.

    Returns the same shape as a row page — visible rows, the annotation, and the
    columns withheld across all of them — so an embedded child grid renders
    through exactly the same contract as a top-level one. A second contract for
    embedded grids is how a restricted stub comes to render as blank in one
    place and as a stub in another.
    """
    if not context.parent_decision.visible:
        # A child of an invisible parent is absent, not forbidden. Returning
        # anything else — including a count — discloses that the parent exists.
        return [], _empty_annotation(), frozenset()

    ordered = _ordered(rows, context.collection)
    decisions = [
        compose(child_rule_set, child_compiled, principal, row, context) for row in ordered
    ]
    return trim_page(ordered, decisions, scope="children")


def _ordered(rows: list[dict[str, Any]], collection: ChildCollection) -> list[dict[str, Any]]:
    """Children in their declared order, with a stable tie-break.

    Line items are a sequence a human curated; returning them in store order
    means the same invoice reads differently on two loads. Falling back to the
    document id keeps that stable when the ordering field is absent or equal.
    """
    field_id = collection.ordering_field

    def key(row: dict[str, Any]) -> tuple[int, Any, str]:
        value = row.get("values", {}).get(field_id) if field_id else None
        # Missing sorts last rather than first: an unordered item appended to a
        # curated list belongs at the end, not at the top.
        return (1 if value is None else 0, value if value is not None else 0, row.get("id", ""))

    return sorted(rows, key=key)


def _empty_annotation() -> Any:
    from lib.permissions.model import Annotation

    return Annotation(visible=0, withheld=0, scope="children")


def parent_snapshot(
    parent_compiled: CompiledBlueprint, parent_values: dict[str, Any]
) -> dict[str, Any]:
    """Exactly the parent fields any permission rule reads — no more.

    Bounded on purpose. Copying the whole parent would put fields the child's
    reader may not see onto a document they can fetch, turning denormalisation
    into a disclosure. Copying nothing would mean fetching the parent for every
    child on every read, which is what makes an embedded grid slow enough that
    someone eventually caches the decision.
    """
    return {
        field_id: parent_values.get(field_id)
        for field_id in sorted(parent_compiled.rule_referenced_fields)
    }


def child_document(
    child_id: str,
    collection_id: str,
    values: dict[str, Any],
    parent: dict[str, Any],
    *,
    workspace_id: str,
    blueprint_id: str,
    parent_row_id: str,
) -> dict[str, Any]:
    """A child row as stored.

    ``collectionId`` is a FIELD, not the collection's name. Every child of every
    Blueprint lives in a collection literally called ``children``, so one
    collection-group index set covers every Blueprint that will ever exist — a
    collection per named child collection would multiply index definitions per
    Blueprint against a hard per-database cap.
    """
    return {
        "id": child_id,
        "collectionId": collection_id,
        "values": values,
        "workspaceId": workspace_id,
        "blueprintId": blueprint_id,
        "parentRowId": parent_row_id,
        PARENT_SNAPSHOT: parent,
    }


def restamp_needed(
    parent_compiled: CompiledBlueprint, changed_fields: tuple[str, ...]
) -> bool:
    """Whether a parent write invalidates its children's denormalised copy.

    Only rule-referenced fields matter. Re-stamping on every parent write would
    turn a one-field edit into a fan-out across two hundred children; never
    re-stamping leaves a stale copy, and a stale rule-referenced value is a
    permission decision made on facts that are no longer true.
    """
    return bool(set(changed_fields) & parent_compiled.rule_referenced_fields)
