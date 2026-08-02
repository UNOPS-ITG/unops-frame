"""``compile_blueprint`` — the Blueprint document turned into the thing every
consumer actually reads.

Nothing downstream parses a raw Blueprint. The grid, the generated API, the
validator, the permission evaluator, the indexer and the replicator all consume
a ``CompiledBlueprint``, cached by ``(blueprint_id, version)``. One parse, one
shape, and a change to the document model touches one file.

**The indexable projection is the important part of this module**, and it exists
to resolve a contradiction the PRDs did not: saved views are user-authored data
with arbitrary filters and sorts (GR-11), while Firestore composite indexes are
declared, deployed artifacts capped at 1,000 per database. A user saving a new
filter-plus-sort combination would need an index that a data write cannot
create.

The resolution is to index *generic slots* rather than *fields*. At publish
time, declared-filterable fields are assigned equality tokens (`fld_state=open`)
that live in one array field, and declared-sortable fields are assigned typed
generic slots (`num0..num7`, `date0..date7`, `txt0..txt7`). A small fixed
repo-declared index template set then covers every view anyone can author, and
the index count becomes O(slots) rather than O(Blueprints x view shapes).

The slot budget is a real product constraint that users feel as "you cannot sort
by this column server-side", so it is surfaced (``slot_pressure``) rather than
silently exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from lib.blueprint.model import Blueprint, FieldDef
from lib.blueprint.registry import FieldTypeRegistry, get_registry
from lib.blueprint.validate import ValidationReport, validate_blueprint

# Slot counts per type. Deliberately small: every slot is an indexed column on
# every row of every Blueprint, so widening this is a write-amplification and
# index-cost decision, not a convenience.
SLOTS = {"num": 8, "date": 8, "txt": 8}

# Which storage kinds can occupy which slot family.
_SLOT_FAMILY = {
    "number": "num",
    "timestamp": "date",
    "string": "txt",
}


@dataclass(frozen=True, slots=True)
class CompiledField:
    definition: FieldDef
    storage: str
    is_restricted: bool
    """At or above the restricted threshold (BP-3b). Precomputed because PM-10
    read-audit, SR-6 index exclusion, NT-9 content safety and bound-Sheet
    exclusion all ask this question on every row."""

    eq_token_prefix: str | None = None
    """`fld_state` — the prefix for equality tokens on this field."""

    sort_slot: str | None = None
    """`num0`, `date2`, `txt1` — the generic column this field's value is
    mirrored into so it can be sorted and range-filtered server-side."""


@dataclass(frozen=True, slots=True)
class IndexPlan:
    """What the row projection carries so the fixed index templates can serve
    any view a user authors."""

    eq_fields: tuple[str, ...]
    sort_slots: dict[str, str]          # field_id -> slot name
    slot_pressure: dict[str, str]       # family -> "used/available"
    unassignable: tuple[str, ...]       # declared sortable but no slot left


@dataclass(frozen=True, slots=True)
class CompiledBlueprint:
    blueprint: Blueprint
    fields: dict[str, CompiledField]
    index_plan: IndexPlan
    rule_referenced_fields: frozenset[str]
    """Every field any permission rule reads.

    Feeds two things: the child re-stamp fan-out (a child denormalises exactly
    these from its parent so PM-3 evaluation needs no extra reads), and BP-17's
    promotion report of absent values per rule-referenced field.
    """

    title_field: str | None
    searchable_fields: tuple[str, ...]
    materialized_formulas: tuple[str, ...]
    read_time_formulas: tuple[str, ...]

    @property
    def id(self) -> str:
        return self.blueprint.id

    @property
    def version(self) -> int:
        return self.blueprint.version

    def field(self, field_id: str) -> CompiledField | None:
        return self.fields.get(field_id)

    def restricted_field_ids(self) -> frozenset[str]:
        return frozenset(fid for fid, f in self.fields.items() if f.is_restricted)


class CompilationError(RuntimeError):
    """A Blueprint that fails BP-26 is never compiled.

    Refusing here rather than compiling a broken document is what stops an
    incoherent Blueprint reaching the grid, the API and the indexer and failing
    differently in each.
    """

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(f"Blueprint failed validation:\n{report}")


def compile_blueprint(
    bp: Blueprint, registry: FieldTypeRegistry | None = None, *, validate: bool = True
) -> CompiledBlueprint:
    reg = registry or get_registry()

    if validate:
        report = validate_blueprint(bp, reg)
        if not report.ok:
            raise CompilationError(report)

    compiled: dict[str, CompiledField] = {}
    plan = _plan_indexes(bp, reg)

    for f in bp.fields:
        ftype = reg.get(f.type)
        storage = ftype.storage if ftype else "string"
        compiled[f.id] = CompiledField(
            definition=f,
            storage=storage,
            is_restricted=reg.bands.is_at_or_above_restricted(f.sensitivity),
            eq_token_prefix=f"fld_{f.id}" if f.id in plan.eq_fields else None,
            sort_slot=plan.sort_slots.get(f.id),
        )

    return CompiledBlueprint(
        blueprint=bp,
        fields=compiled,
        index_plan=plan,
        rule_referenced_fields=_rule_referenced_fields(bp),
        title_field=bp.view_defaults.title_field,
        searchable_fields=tuple(
            f.id
            for f in bp.fields
            # A restricted value is never indexed. The utility loss is accepted
            # and measured (SR-6); an index is a copy of your data and a
            # careless one is a permission bypass with a query box.
            if f.searchable and not reg.bands.is_at_or_above_restricted(f.sensitivity)
        ),
        materialized_formulas=tuple(f.id for f in bp.fields if f.type == "formula" and f.materialized),
        read_time_formulas=tuple(f.id for f in bp.fields if f.type == "formula" and not f.materialized),
    )


def _plan_indexes(bp: Blueprint, reg: FieldTypeRegistry) -> IndexPlan:
    eq_fields: list[str] = []
    sort_slots: dict[str, str] = {}
    used = {family: 0 for family in SLOTS}
    unassignable: list[str] = []

    for f in bp.fields:
        if not f.indexed:
            continue
        ftype = reg.get(f.type)
        if ftype is None:
            continue

        # Equality tokens are unbounded: they all live in one array field, so an
        # extra filterable field costs an array entry rather than an index.
        if f.in_filter_bar or f.indexed:
            eq_fields.append(f.id)

        # Sort slots are the scarce resource.
        family = _SLOT_FAMILY.get(ftype.storage)
        if family is None:
            continue
        if used[family] < SLOTS[family]:
            sort_slots[f.id] = f"{family}{used[family]}"
            used[family] += 1
        else:
            unassignable.append(f.id)

    return IndexPlan(
        eq_fields=tuple(eq_fields),
        sort_slots=sort_slots,
        slot_pressure={fam: f"{used[fam]}/{SLOTS[fam]}" for fam in SLOTS},
        unassignable=tuple(unassignable),
    )


def _rule_referenced_fields(bp: Blueprint) -> frozenset[str]:
    referenced: set[str] = set()
    for rule in bp.permissions:
        referenced.update(rule.field_ids or ())
        if rule.row_condition:
            referenced.update(_fields_in_expression(rule.row_condition))
    return frozenset(referenced)


def _fields_in_expression(node: Any) -> set[str]:
    """Walk a shared-grammar AST for field references.

    Expressions are stored as AST, never as strings (BP-9), which is exactly
    what makes this a tree walk rather than a regex over user text — and what
    makes the answer reliable enough to drive a permission-critical fan-out.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        if node.get("type") == "field" and isinstance(node.get("id"), str):
            found.add(node["id"])
        for value in node.values():
            found |= _fields_in_expression(value)
    elif isinstance(node, list):
        for item in node:
            found |= _fields_in_expression(item)
    return found


def build_row_projection(compiled: CompiledBlueprint, values: dict[str, Any]) -> dict[str, Any]:
    """The generic index columns written alongside a row's values.

    ``eq`` is one array of ``fld_<id>=<value>`` tokens served by
    ``array-contains-any``; the typed slots mirror sortable values. Note the
    single-clause constraint this design lives under: Firestore permits one
    ``array-contains-any`` per query, so AND-ed equality predicates beyond the
    first are served from typed slots or post-filtered — which the query
    compiler decides, not this function.
    """
    projection: dict[str, Any] = {}

    tokens = [
        f"fld_{fid}={values[fid]}"
        for fid in compiled.index_plan.eq_fields
        if values.get(fid) is not None and not isinstance(values.get(fid), (dict, list))
    ]
    if tokens:
        projection["eq"] = tokens

    for field_id, slot in compiled.index_plan.sort_slots.items():
        value = values.get(field_id)
        if value is not None and not isinstance(value, (dict, list)):
            projection[slot] = value

    return projection


@lru_cache(maxsize=512)
def _cached(blueprint_json: str) -> CompiledBlueprint:
    return compile_blueprint(Blueprint.model_validate_json(blueprint_json))


def compile_cached(bp: Blueprint) -> CompiledBlueprint:
    """Compile once per (blueprint, version).

    Keyed on the serialised document rather than on ``(id, version)`` so that an
    unversioned edit during development cannot serve a stale compilation — a
    class of bug that presents as "my change did nothing".
    """
    return _cached(bp.model_dump_json())
