"""Blueprint coherence validation (BP-26).

Frame's **only** Blueprint-time validator. Every other check that wants to run
at save — permission verb dependencies, reverse-link targets, grammar scope,
lifecycle exclusivity — is a check in this one suite, reported in one output, so
a steward fixes everything in one pass instead of playing whack-a-mole with
sequential errors.

This matters more here than in a hand-authored system, because BP-16 and BP-17
have an **AI drafting the model**. An unguarded AI-generated Blueprint with a
hidden required field and no default is a Blueprint nobody can ever save a row
against, and it will be reported as a platform bug rather than a modelling
mistake.

Checks never raise on the first problem. They collect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from lib.blueprint.model import Blueprint, Tier
from lib.blueprint.registry import FieldTypeRegistry, get_registry
from lib.grammar.analyse import analyse
from lib.grammar.ast import ExpressionError, Scope, parse

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

# Names Frame uses on every row document. A field id colliding with one would be
# silently shadowed by system metadata on write.
RESERVED_FIELD_IDS = frozenset(
    {
        "id", "version", "created_at", "created_by", "updated_at", "updated_by",
        "lifecycle_status", "amended_from", "blueprint_id", "blueprint_version",
        "workspace_id", "parent_id", "collection_id", "values", "field_versions",
        "eq", "deleted", "deleted_at",
    }
)

# Types that cannot participate in a composite index: a full-text value would
# blow the per-document index-entry budget.
UNINDEXABLE_VARIANTS = frozenset({"long", "rich"})


@dataclass(frozen=True, slots=True)
class Problem:
    check: str
    message: str
    field_id: str | None = None

    def __str__(self) -> str:
        where = f" [{self.field_id}]" if self.field_id else ""
        return f"{self.check}{where}: {self.message}"


@dataclass
class ValidationReport:
    problems: list[Problem] = dc_field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, check: str, message: str, field_id: str | None = None) -> None:
        self.problems.append(Problem(check=check, message=message, field_id=field_id))

    def __str__(self) -> str:
        if self.ok:
            return "Blueprint is coherent."
        return "\n".join(str(p) for p in self.problems)


def validate_blueprint(bp: Blueprint, registry: FieldTypeRegistry | None = None) -> ValidationReport:
    reg = registry or get_registry()
    report = ValidationReport()

    _check_field_identity(bp, reg, report)
    _check_field_properties(bp, reg, report)
    _check_conditionality(bp, report)
    _check_relationships(bp, report)
    _check_view_defaults(bp, report)
    _check_permissions(bp, report)
    _check_lifecycle(bp, report)
    _check_naming(bp, report)
    _check_expressions(bp, report)
    return report


# Which scope each expression slot may read from. The rule this table encodes:
# a value that is materialised, replicated or indexed may never be computed
# above ROW_PARENT, because a stored value that varies by reader is not a value.
_SLOT_SCOPE = {
    "expression": Scope.ROW,          # formula fields are stored
    "validation": Scope.ROW,          # runs on write, before a reader exists
    "visible_when": Scope.ROW_PARENT,
    "required_when": Scope.ROW_PARENT,
    "read_only_when": Scope.ROW_PARENT,
    "row_condition": Scope.ROW_PARENT_SUBJECT,  # permission rules see the principal
}
_SCOPE_RANK = {Scope.ROW: 0, Scope.ROW_PARENT: 1, Scope.ROW_PARENT_SUBJECT: 2}


def _check_expressions(bp: Blueprint, r: ValidationReport) -> None:
    """Parse every expression, and check what it reads against what its slot allows.

    Expressions are stored as AST rather than as strings (BP-9), so this is a
    structural check rather than a regex over user text — which is what makes it
    trustworthy enough to gate a permission rule on.
    """
    known_fields = {f.id for f in bp.fields}

    def check(raw: dict[str, Any] | None, slot: str, where: str, field_id: str | None = None) -> None:
        if raw is None:
            return
        try:
            expr = parse(raw)
        except ExpressionError as exc:
            r.add("expression", f"{where}: {exc}", field_id)
            return

        analysis = analyse(expr)
        allowed = _SLOT_SCOPE[slot]
        if _SCOPE_RANK[analysis.required_scope] > _SCOPE_RANK[allowed]:
            r.add(
                "expression-scope",
                f"{where} may only read {allowed.value} scope, but this expression needs "
                f"{analysis.required_scope.value}",
                field_id,
            )

        for referenced in sorted(analysis.fields):
            if referenced not in known_fields:
                r.add("expression", f"{where} references unknown field {referenced!r}", field_id)

    for f in bp.fields:
        check(f.expression, "expression", "formula", f.id)
        check(f.visible_when, "visible_when", "visible_when", f.id)
        check(f.required_when, "required_when", "required_when", f.id)
        check(f.read_only_when, "read_only_when", "read_only_when", f.id)
        if f.validation and f.validation.condition:
            check(f.validation.condition, "validation", "validation condition", f.id)

    for i, rule in enumerate(bp.permissions):
        check(rule.row_condition, "row_condition", f"rule[{i}] row condition")

    for i, t in enumerate(bp.transitions):
        # A transition gate is evaluated for a specific actor, so it sees the
        # subject — but never an external system: no integration may block a
        # transition (AU-10), so there is nothing here that can call out.
        check(t.condition, "row_condition", f"transition[{i}] condition")


def _check_field_identity(bp: Blueprint, reg: FieldTypeRegistry, r: ValidationReport) -> None:
    seen: set[str] = set()
    for f in bp.fields:
        if not _IDENTIFIER.match(f.id):
            r.add("field-id", "must be lower snake_case, starting with a letter", f.id)
        if f.id in RESERVED_FIELD_IDS:
            r.add("field-id", "collides with a reserved system name", f.id)
        if f.id in seen:
            r.add("field-id", "duplicate field id", f.id)
        seen.add(f.id)

        ftype = reg.get(f.type)
        if ftype is None:
            r.add("field-type", f"unknown field type {f.type!r}", f.id)
            continue
        if not ftype.enabled:
            # A more useful message than "unknown type": the type exists and is
            # simply not available yet.
            r.add("field-type", f"type {f.type!r} is declared but not available until {ftype.phase}", f.id)
        if f.variant and ftype.variants and f.variant not in ftype.variants:
            r.add("field-type", f"variant {f.variant!r} is not one of {list(ftype.variants)}", f.id)


def _check_field_properties(bp: Blueprint, reg: FieldTypeRegistry, r: ValidationReport) -> None:
    for f in bp.fields:
        ftype = reg.get(f.type)
        if ftype is None or not ftype.enabled:
            continue

        # The classic unsaveable Blueprint, and the one an AI draft produces.
        if f.required and f.hidden and f.default is None:
            r.add(
                "unsaveable",
                "field is required and hidden with no default, so no row can ever be saved",
                f.id,
            )

        if f.unique and not ftype.allows("unique"):
            r.add("unique", f"unique is not meaningful on a {f.type} field", f.id)

        if f.indexed and not ftype.allows("indexed"):
            r.add("indexed", f"a {f.type} field cannot be indexed", f.id)
        if f.indexed and f.variant in UNINDEXABLE_VARIANTS:
            r.add("indexed", f"a {f.variant} text field cannot be indexed", f.id)

        if f.searchable and not ftype.allows("searchable"):
            r.add("searchable", f"a {f.type} field cannot be searchable", f.id)

        if f.options and not ftype.allows("options"):
            r.add("options", f"a {f.type} field does not take options", f.id)
        if ftype.allows("options") and not f.options:
            r.add("options", "select fields must declare at least one option", f.id)

        if f.options:
            keys = [o.key for o in f.options]
            if len(keys) != len(set(keys)):
                r.add("options", "duplicate option keys", f.id)
            if f.default is not None and f.default not in keys:
                r.add("default", f"default {f.default!r} is not one of the declared options", f.id)

        if f.type == "boolean" and f.default is not None and not isinstance(f.default, bool):
            r.add("default", "a checkbox default must be true or false", f.id)

        if f.render_as and ftype.render_as and f.render_as not in ftype.render_as:
            r.add("render-as", f"{f.render_as!r} is not one of {list(ftype.render_as)}", f.id)

        if f.sensitivity not in reg.bands.by_band:
            r.add("sensitivity", f"band {f.sensitivity} is not a declared sensitivity band", f.id)

        if f.type == "formula":
            if f.expression is None:
                r.add("formula", "a formula field must declare an expression", f.id)
            if not f.materialized and (f.indexed or f.searchable):
                r.add(
                    "formula",
                    "a read-time formula has no stored column, so it cannot be indexed or searchable",
                    f.id,
                )
        elif f.expression is not None:
            r.add("formula", "only a formula field may declare an expression", f.id)


def _check_conditionality(bp: Blueprint, r: ValidationReport) -> None:
    for f in bp.fields:
        # A field that must be filled but cannot be seen is unsatisfiable, and the
        # user is given no way to discover why their save fails.
        if f.required_when is not None and f.visible_when is not None:
            if f.required_when == f.visible_when:
                continue  # required exactly when visible: coherent
            r.add(
                "conditionality",
                "required_when and visible_when differ, so the field can be required while "
                "hidden; narrow required_when or make them identical",
                f.id,
            )
        if f.required_when is not None and f.hidden:
            r.add("conditionality", "a permanently hidden field cannot be conditionally required", f.id)


def _check_relationships(bp: Blueprint, r: ValidationReport) -> None:
    child_ids = {c.id for c in bp.children}
    if len(child_ids) != len(bp.children):
        r.add("children", "duplicate child collection ids")

    for c in bp.children:
        if c.blueprint == bp.id:
            r.add("children", f"child collection {c.id!r} targets its own Blueprint")
        if c.max_rows > 200:
            # children + parent + 1 audit + 1 outbox <= 500 per commit.
            r.add(
                "children",
                f"max_rows {c.max_rows} exceeds the 200 the transactional save budget allows",
            )

    for f in bp.fields:
        if f.type == "reference" and not f.target:
            r.add("reference", "a reference field must declare a target Blueprint", f.id)
        if f.type == "reference" and f.target in child_ids:
            r.add("reference", "a reference must not point at this Blueprint's own child", f.id)
        if f.type == "corporate_reference" and not f.dimension:
            r.add("corporate", "a corporate reference must declare a dimension", f.id)


def _check_view_defaults(bp: Blueprint, r: ValidationReport) -> None:
    ids = {f.id for f in bp.fields}
    vd = bp.view_defaults

    # Every consumer assumes a row can be named: reference chips, notification
    # subjects, search results, generated filenames, audit entries.
    if bp.tier is not Tier.PERSONAL and not vd.title_field:
        r.add("view-defaults", f"title_field is mandatory at {bp.tier} tier")

    for name, value in (("title_field", vd.title_field), ("subtitle_field", vd.subtitle_field),
                        ("default_sort", vd.default_sort)):
        if value and value not in ids:
            r.add("view-defaults", f"{name} references unknown field {value!r}")
    for value in vd.search_fields:
        if value not in ids:
            r.add("view-defaults", f"search_fields references unknown field {value!r}")
    for value in vd.default_columns:
        if value not in ids:
            r.add("view-defaults", f"default_columns references unknown field {value!r}")


# Verb dependencies, validated here rather than restated in PRD 05's prose.
_VERB_REQUIRES = {"publish": "read", "import": "create", "change_state": "update", "export": "read"}
_KNOWN_ACTIONS = frozenset(
    {"read", "select", "create", "import", "update", "delete", "change_state", "export", "publish", "manage"}
)


def _check_permissions(bp: Blueprint, r: ValidationReport) -> None:
    ids = {f.id for f in bp.fields}
    for i, rule in enumerate(bp.permissions):
        label = f"rule[{i}]"
        if not rule.principals:
            r.add("permissions", f"{label} names no principals")

        actions = set(rule.actions)
        for action in actions:
            if action not in _KNOWN_ACTIONS:
                r.add("permissions", f"{label} uses unknown action {action!r}")
            required = _VERB_REQUIRES.get(action)
            if required and required not in actions and rule.effect == "allow":
                r.add("permissions", f"{label} grants {action!r} without {required!r}")

        for fid in rule.field_ids or ():
            if fid not in ids:
                r.add("permissions", f"{label} references unknown field {fid!r}")

        if rule.masked:
            r.add("permissions", f"{label} sets masked, which is reserved and not available until P2")


def _check_lifecycle(bp: Blueprint, r: ValidationReport) -> None:
    lc = bp.lifecycle

    # Submittable is for records corrected by amendment; freeze is for records
    # corrected not at all. A Blueprint claiming both has no coherent answer to
    # "this approved record is wrong".
    if lc.submittable and lc.freeze_on_state:
        r.add("lifecycle", "a Blueprint declares either the submittable lifecycle or a freeze policy, never both")

    if lc.submittable:
        r.add("lifecycle", "the submittable lifecycle is reserved and not available until P2")

    state_keys = {s.key for s in bp.states}
    if len(state_keys) != len(bp.states):
        r.add("workflow", "duplicate state keys")

    if lc.freeze_on_state and lc.freeze_on_state not in state_keys:
        r.add("lifecycle", f"freeze_on_state references unknown state {lc.freeze_on_state!r}")

    for t in bp.transitions:
        if t.from_state not in state_keys:
            r.add("workflow", f"transition from unknown state {t.from_state!r}")
        if t.to_state not in state_keys:
            r.add("workflow", f"transition to unknown state {t.to_state!r}")

    # No path may reach a submitted state from a cancelled one (BP-22).
    cancelled = {s.key for s in bp.states if s.lifecycle_status == "cancelled"}
    submitted = {s.key for s in bp.states if s.lifecycle_status == "submitted"}
    for t in bp.transitions:
        if t.from_state in cancelled and t.to_state in submitted:
            r.add("lifecycle", f"transition {t.from_state!r} -> {t.to_state!r} revives a cancelled record")


def _check_naming(bp: Blueprint, r: ValidationReport) -> None:
    ids = {f.id for f in bp.fields}
    if bp.naming.rule == "by_field":
        if not bp.naming.field_id:
            r.add("naming", "by_field naming must declare a field_id")
        elif bp.naming.field_id not in ids:
            r.add("naming", f"naming field {bp.naming.field_id!r} does not exist")
        else:
            source = bp.field(bp.naming.field_id)
            if source is not None and not source.unique:
                r.add("naming", "a field used as the display identifier must be unique", source.id)
    if bp.naming.rule == "series" and not bp.naming.series_pattern:
        r.add("naming", "series naming must declare a pattern")
    if bp.naming.rule == "series":
        r.add("naming", "series naming is reserved and not available until P2")
