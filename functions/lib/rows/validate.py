"""BP-4: the single validation path.

Every channel — grid edit, bulk paste, CSV import, admin API, undo, and later
forms, automations, bound Sheets, MCP and inbound webhooks — reaches this
function. Two paths is the defect class that produces "it validates in the grid
but not on import" for the life of the product.

The first thing it does is **restore stored values for fields the writer cannot
write**. That clause is not hypothetical: Frappe shipped the same masking
mechanism and immediately hit both failure modes — numeric types casting the
placeholder back to zero, and clients posting the placeholder straight back on
save, overwriting real data. A restricted stub is never a value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from lib.grammar.ast import parse
from lib.grammar.evaluate import Context, matches
from lib.permissions.model import Decision

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint


@dataclass(frozen=True, slots=True)
class FieldError:
    field_id: str
    message: str
    code: str


@dataclass(slots=True)
class ValidationOutcome:
    values: dict[str, Any] = dc_field(default_factory=dict)
    errors: list[FieldError] = dc_field(default_factory=list)
    rejected_fields: list[str] = dc_field(default_factory=list)
    """Fields the caller tried to write but may not.

    Reported rather than silently ignored or reverted: a client that believes it
    wrote something it did not is worse off than one that got an error.
    """

    @property
    def ok(self) -> bool:
        return not self.errors and not self.rejected_fields


class ValidationRejection(Exception):
    def __init__(self, outcome: ValidationOutcome) -> None:
        self.outcome = outcome
        super().__init__("write rejected by validation")


def validate_write(
    compiled: CompiledBlueprint,
    *,
    submitted: dict[str, Any],
    stored: dict[str, Any] | None,
    decision: Decision,
    is_create: bool,
) -> ValidationOutcome:
    """Validate one row write. The only place validation happens."""
    stored = stored or {}
    outcome = ValidationOutcome()

    # 1. Restore what the writer cannot write, BEFORE any rule runs.
    merged: dict[str, Any] = dict(stored)
    for field_id, value in submitted.items():
        cf = compiled.field(field_id)
        if cf is None:
            outcome.errors.append(FieldError(field_id, "unknown field", "unknown_field"))
            continue
        if _is_restricted_stub(value):
            # Never accepted from a request body on any channel. Silently
            # ignoring it would be kinder-looking and would still let a
            # round-tripped stub blank a field on the next save.
            outcome.rejected_fields.append(field_id)
            continue
        if not is_create and field_id not in decision.writable_fields:
            outcome.rejected_fields.append(field_id)
            continue
        if cf.definition.read_only:
            outcome.rejected_fields.append(field_id)
            continue
        if cf.definition.set_once and not is_create and stored.get(field_id) not in (None, ""):
            outcome.errors.append(
                FieldError(field_id, "may only be set once", "set_once")
            )
            continue
        merged[field_id] = value

    if outcome.rejected_fields:
        # 403 rather than a quiet revert, naming the fields.
        return outcome

    # 2. Defaults, for a create.
    if is_create:
        for field_id, cf in compiled.fields.items():
            if field_id not in merged and cf.definition.default is not None:
                merged[field_id] = cf.definition.default

    # 3. Declarative rules, against the merged row.
    ctx = Context(row=merged, scope=_row_scope())
    for field_id, cf in compiled.fields.items():
        definition = cf.definition
        value = merged.get(field_id)

        required = definition.required
        if definition.required_when is not None:
            # Conditional requiredness is enforced HERE, on every channel —
            # which is the reason BP-3a moved it onto the field rather than
            # leaving it in the form builder.
            required = matches(parse(definition.required_when), ctx)

        if required and _is_blank(value):
            outcome.errors.append(FieldError(field_id, "is required", "required"))
            continue

        if _is_blank(value):
            continue

        outcome.errors.extend(_check_type(field_id, cf, value))
        outcome.errors.extend(_check_rules(field_id, cf, value, ctx))

    outcome.values = merged
    return outcome


def _row_scope() -> Any:
    from lib.grammar.ast import Scope

    # Validation runs on write, before any reader exists, so it cannot see the
    # acting principal — a rule that did would make validity vary by who saved.
    return Scope.ROW


def _is_restricted_stub(value: Any) -> bool:
    return isinstance(value, dict) and value.get("restricted") is True


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, list) and not value)


def _check_type(field_id: str, cf: Any, value: Any) -> list[FieldError]:
    errors: list[FieldError] = []
    storage = cf.storage

    match storage:
        case "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(FieldError(field_id, "must be a number", "type"))
        case "boolean":
            if not isinstance(value, bool):
                errors.append(FieldError(field_id, "must be true or false", "type"))
        case "timestamp":
            if not isinstance(value, (datetime, date, str)):
                errors.append(FieldError(field_id, "must be a date", "type"))
        case "string" | "corporate_ref":
            if not isinstance(value, (str, dict)):
                errors.append(FieldError(field_id, "must be text", "type"))
        case "string_array":
            if not isinstance(value, list):
                errors.append(FieldError(field_id, "must be a list", "type"))

    options = cf.definition.options
    if options and isinstance(value, str):
        keys = {o.key for o in options}
        if value not in keys:
            errors.append(FieldError(field_id, f"must be one of {sorted(keys)}", "options"))
    if options and isinstance(value, list):
        keys = {o.key for o in options}
        unknown = [v for v in value if v not in keys]
        if unknown:
            errors.append(FieldError(field_id, f"unknown options {unknown}", "options"))

    return errors


def _check_rules(field_id: str, cf: Any, value: Any, ctx: Context) -> list[FieldError]:
    rule = cf.definition.validation
    if rule is None:
        return []

    errors: list[FieldError] = []

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if rule.min is not None and value < rule.min:
            errors.append(FieldError(field_id, f"must be at least {rule.min}", "min"))
        if rule.max is not None and value > rule.max:
            errors.append(FieldError(field_id, f"must be at most {rule.max}", "max"))

    if isinstance(value, str):
        if rule.min_length is not None and len(value) < rule.min_length:
            errors.append(FieldError(field_id, f"must be at least {rule.min_length} characters", "min_length"))
        if rule.max_length is not None and len(value) > rule.max_length:
            errors.append(FieldError(field_id, f"must be at most {rule.max_length} characters", "max_length"))
        if rule.regex is not None and not re.match(rule.regex, value):
            errors.append(FieldError(field_id, "is not in the expected format", "regex"))
        if rule.allowed_values is not None and value not in rule.allowed_values:
            errors.append(FieldError(field_id, "is not an allowed value", "allowed_values"))

    if rule.condition is not None and not matches(parse(rule.condition), ctx):
        # A cross-field rule that cannot be evaluated (because another field is
        # blank) is UNKNOWN, which `matches` treats as not-matched — so it does
        # not block a partial save. Blocking on unknown would make it impossible
        # to fill a form in any order but one.
        errors.append(FieldError(field_id, "fails a cross-field rule", "condition"))

    return errors
