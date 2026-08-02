"""The in-memory evaluator. Authoritative.

Where the query compiler and this disagree, this is right and the compiler has a
bug — which is what the conformance suite asserts.

Three semantics are pinned down here because leaving them implicit is what makes
an expression language unfixable later. Each is a decision, not an accident:

**Missing is not null is not empty — but comparisons treat them alike.** A field
absent from a row, a field explicitly null, and a field set to "" all compare as
UNKNOWN rather than as False. That distinction is what makes
``NOT (amount > 100)`` behave correctly on a row with no amount: it stays
unknown rather than becoming true.

**Unknown propagates, three-valued.** ``unknown AND false`` is false;
``unknown AND true`` is unknown; ``unknown OR true`` is true. SQL's rules,
because they are the ones that survive contact with a partly-populated table —
and BP-15 makes half-populated rows the designed-for norm at exactly the moment
promotion attaches permission rules to them.

**Datetimes are UTC-normalised before comparison.** A naive datetime is read as
UTC rather than as local time. Reading a stored timestamp as local time is how a
report silently shifts by hours depending on which machine ran it.

The caller decides what UNKNOWN means for its purpose: a permission rule treats
it as "not matched" (PM-2), a validation rule as "cannot evaluate, do not
block", a formula as null.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from lib.grammar.ast import (
    Binary,
    BinaryOp,
    Call,
    Expr,
    FieldRef,
    FunctionName,
    If,
    In,
    IsEmpty,
    Literal_,
    Logical,
    LogicalOp,
    Not,
    ParentFieldRef,
    Scope,
    SubjectRef,
)


class Unknown:
    """The third truth value. A singleton so ``is UNKNOWN`` works."""

    _instance: Unknown | None = None

    def __new__(cls) -> Unknown:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        raise TypeError(
            "UNKNOWN has no truth value — decide explicitly what it means here. "
            "A permission rule treats it as not-matched; a validation rule as "
            "cannot-evaluate."
        )


UNKNOWN = Unknown()


@dataclass(frozen=True, slots=True)
class Subject:
    email: str | None = None
    subject: str | None = None
    groups: frozenset[str] = frozenset()


@dataclass(slots=True)
class Context:
    row: dict[str, Any] = dc_field(default_factory=dict)
    parent: dict[str, Any] | None = None
    subject: Subject | None = None
    scope: Scope = Scope.ROW
    now: datetime | None = None
    """Injected rather than read from the clock, so evaluation is deterministic
    and a test can pin 'today'."""

    def clock(self) -> datetime:
        return self.now or datetime.now(UTC)


class ScopeViolation(ValueError):
    """An expression read something its scope forbids.

    Raised rather than evaluated-to-unknown: a formula reaching for the acting
    principal is a modelling error that must surface at Blueprint save, not a
    value that quietly differs per reader.
    """


def _normalise(value: Any) -> Any:
    """Datetimes to UTC-aware; dates to midnight UTC, so a date and a datetime
    are comparable without the caller thinking about it."""
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    return value


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value is UNKNOWN


def evaluate(expr: Expr, ctx: Context) -> Any:
    """Evaluate to a value, or UNKNOWN."""
    match expr:
        case Literal_():
            return expr.value

        case FieldRef():
            value = ctx.row.get(expr.id, UNKNOWN)
            # A restricted stub is not a value. Treating {"restricted": True} as
            # data would let a rule branch on whether a field was withheld,
            # which leaks the very thing the trim exists to hide.
            if isinstance(value, dict) and value.get("restricted"):
                return UNKNOWN
            return UNKNOWN if value is None else _normalise(value)

        case ParentFieldRef():
            if ctx.scope is Scope.ROW:
                raise ScopeViolation(
                    f"parent_field {expr.id!r} is not readable at row scope; a materialised, "
                    "replicated or indexed value may not depend on its parent"
                )
            if ctx.parent is None:
                return UNKNOWN
            value = ctx.parent.get(expr.id, UNKNOWN)
            return UNKNOWN if value is None else _normalise(value)

        case SubjectRef():
            if ctx.scope is not Scope.ROW_PARENT_SUBJECT:
                raise ScopeViolation(
                    f"subject.{expr.attribute} is only readable in a permission rule, view "
                    "filter, automation condition or search term — never in a stored value"
                )
            if expr.attribute == "now":
                return ctx.clock()
            if ctx.subject is None:
                return UNKNOWN
            got = getattr(ctx.subject, expr.attribute, None)
            return UNKNOWN if got is None else got

        case Binary():
            return _binary(expr, ctx)

        case Logical():
            return _logical(expr, ctx)

        case Not():
            inner = evaluate(expr.operand, ctx)
            if inner is UNKNOWN:
                return UNKNOWN
            return not _truthy(inner)

        case In():
            value = evaluate(expr.value, ctx)
            if value is UNKNOWN:
                return UNKNOWN
            options = [evaluate(o, ctx) for o in expr.options]
            if any(o is UNKNOWN for o in options):
                return UNKNOWN
            # A membership test against a group set is the PM-2a allow-list
            # shape, and it is the one condition form that always pushes down.
            for option in options:
                if isinstance(option, (set, frozenset)):
                    if value in option:
                        return True
                elif option == value:
                    return True
            return False

        case IsEmpty():
            # The one operator that can SEE missingness rather than propagating
            # it, which is what makes "this field is not filled in" expressible.
            return _is_missing(evaluate(expr.operand, ctx))

        case If():
            condition = evaluate(expr.condition, ctx)
            if condition is UNKNOWN:
                return UNKNOWN
            return evaluate(expr.then if _truthy(condition) else expr.otherwise, ctx)

        case Call():
            return _call(expr, ctx)

    raise ExpressionEvaluationError(f"unhandled node type {type(expr).__name__}")


class ExpressionEvaluationError(RuntimeError):
    pass


def _truthy(value: Any) -> bool:
    return bool(value)


def _logical(expr: Logical, ctx: Context) -> Any:
    """Three-valued, SQL's rules, and short-circuiting where it is sound."""
    seen_unknown = False
    for operand in expr.operands:
        value = evaluate(operand, ctx)
        if value is UNKNOWN:
            seen_unknown = True
            continue
        if expr.op is LogicalOp.AND and not _truthy(value):
            return False  # false dominates AND, even beside unknown
        if expr.op is LogicalOp.OR and _truthy(value):
            return True  # true dominates OR
    if seen_unknown:
        return UNKNOWN
    return expr.op is LogicalOp.AND


_COMPARISONS = {
    BinaryOp.EQ: lambda a, b: a == b,
    BinaryOp.NEQ: lambda a, b: a != b,
    BinaryOp.LT: lambda a, b: a < b,
    BinaryOp.LTE: lambda a, b: a <= b,
    BinaryOp.GT: lambda a, b: a > b,
    BinaryOp.GTE: lambda a, b: a >= b,
}


def _binary(expr: Binary, ctx: Context) -> Any:
    left = evaluate(expr.left, ctx)
    right = evaluate(expr.right, ctx)

    if expr.op is BinaryOp.CONCAT:
        if left is UNKNOWN or right is UNKNOWN:
            return UNKNOWN
        return f"{left}{right}"

    if _is_missing(left) or _is_missing(right):
        return UNKNOWN

    if expr.op in _COMPARISONS:
        try:
            return _COMPARISONS[expr.op](left, right)
        except TypeError:
            # Comparing a string to a number is a modelling error, not a
            # crash — and never silently False, which would make a permission
            # rule quietly stop matching.
            return UNKNOWN

    try:
        match expr.op:
            case BinaryOp.ADD:
                return left + right
            case BinaryOp.SUB:
                return left - right
            case BinaryOp.MUL:
                return left * right
            case BinaryOp.DIV:
                return UNKNOWN if right == 0 else left / right
    except TypeError:
        return UNKNOWN

    raise ExpressionEvaluationError(f"unhandled operator {expr.op}")


def _call(expr: Call, ctx: Context) -> Any:
    match expr.fn:
        case FunctionName.TODAY:
            now = ctx.clock()
            return datetime(now.year, now.month, now.day, tzinfo=UTC)
        case FunctionName.NOW:
            return ctx.clock()
        case FunctionName.DATEADD:
            if len(expr.args) != 2:
                raise ExpressionEvaluationError("dateadd takes a date and a number of days")
            base = evaluate(expr.args[0], ctx)
            days = evaluate(expr.args[1], ctx)
            if base is UNKNOWN or days is UNKNOWN:
                return UNKNOWN
            if not isinstance(base, datetime) or not isinstance(days, (int, float)):
                return UNKNOWN
            return base + timedelta(days=float(days))

    raise ExpressionEvaluationError(f"unhandled function {expr.fn}")


def matches(expr: Expr, ctx: Context, *, unknown_matches: bool = False) -> bool:
    """Evaluate as a predicate, deciding explicitly what UNKNOWN means.

    ``unknown_matches`` is PM-2's ``strict_attributes``: by default an allow
    grant does not apply to a row with an unpopulated attribute and a deny does
    not fire on one. Frappe's equivalent defaults the other way, so a blank
    restricted field makes a row visible to everyone — which is the failure this
    parameter exists to make explicit rather than accidental.
    """
    result = evaluate(expr, ctx)
    if result is UNKNOWN:
        return unknown_matches
    return _truthy(result)
