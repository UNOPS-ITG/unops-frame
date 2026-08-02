"""The store-query backend.

Turns an expression into what the store can actually serve, plus whatever is
left over for the in-memory evaluator to finish. Two rules govern it.

**The pushdown predicate is defined against the DECLARED INDEX SET, not against
Firestore's abstract capability.** Firestore can express far more than Frame has
indexes for; a compiler that pushed everything Firestore *could* do would emit
queries needing composite indexes that do not exist and cannot be created by a
data write. So a term is push-downable only if it lands on an equality token or
a typed sort slot that ``compile_blueprint`` actually assigned.

**Anything not pushed down is a residual, evaluated in memory, and the caller is
told.** A compiler that silently dropped a term would return rows that do not
match — the worst failure mode for a permission rule. A compiler that silently
post-filtered without saying so would let an unbounded scan look like a query.

The result is deliberately three-part: what to ask the store, what to check
afterwards, and whether the split is affordable.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any

from lib.grammar.ast import (
    AllowListRef,
    Binary,
    BinaryOp,
    Expr,
    FieldRef,
    In,
    Literal_,
    Logical,
    LogicalOp,
)

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint


@dataclass(frozen=True, slots=True)
class StoreFilter:
    """One clause the store can serve, in store terms rather than field terms."""

    path: str          # "eq" or a slot name like "num0"
    op: str            # "array_contains_any" | "==" | "<" | "<=" | ">" | ">=" | "in"
    value: Any


@dataclass(slots=True)
class QueryPlan:
    filters: list[StoreFilter] = dc_field(default_factory=list)
    residual: Expr | None = None
    """What the store cannot serve. Evaluated per row by the authoritative
    evaluator after fetching."""

    fully_pushed: bool = True
    reasons: list[str] = dc_field(default_factory=list)
    """Why each unpushed term stayed behind — surfaced to the query engine so a
    view that will be expensive can say so rather than simply being slow."""

    @property
    def needs_post_filter(self) -> bool:
        return self.residual is not None

    def note(self, reason: str) -> None:
        self.fully_pushed = False
        if reason not in self.reasons:
            self.reasons.append(reason)


def compile_query(
    expr: Expr | None,
    compiled: CompiledBlueprint,
    allow_lists: dict[str, frozenset[str]] | None = None,
) -> QueryPlan:
    """Split an expression into store filters and an in-memory residual.

    ``allow_lists`` are the acting principal's PM-2a scopes. They are resolved
    HERE rather than left as a residual, because expanding them to a literal set
    is exactly what makes the allow-list shape affordable at grid scale.
    """
    allow_lists = allow_lists or {}
    plan = QueryPlan()
    if expr is None:
        return plan

    conjuncts = _flatten_and(expr)
    residuals: list[Expr] = []
    array_clause_used = False

    for term in conjuncts:
        pushed, uses_array = _try_push(term, compiled, plan, array_clause_used, allow_lists)
        if pushed:
            array_clause_used = array_clause_used or uses_array
        else:
            residuals.append(term)

    if residuals:
        plan.residual = residuals[0] if len(residuals) == 1 else Logical(
            op=LogicalOp.AND, operands=residuals
        )
    return plan


def _flatten_and(expr: Expr) -> list[Expr]:
    """Only a top-level AND can be split across store filters.

    An OR cannot: Firestore has no disjunction across different fields that
    Frame indexes for, so an OR goes to the residual whole rather than being
    half-pushed, which would return too few rows.
    """
    if isinstance(expr, Logical) and expr.op is LogicalOp.AND:
        out: list[Expr] = []
        for operand in expr.operands:
            out.extend(_flatten_and(operand))
        return out
    return [expr]


_RANGE_OPS = {
    BinaryOp.LT: "<",
    BinaryOp.LTE: "<=",
    BinaryOp.GT: ">",
    BinaryOp.GTE: ">=",
}


def _try_push(
    term: Expr,
    compiled: CompiledBlueprint,
    plan: QueryPlan,
    array_clause_used: bool,
    allow_lists: dict[str, frozenset[str]],
) -> tuple[bool, bool]:
    """Returns (pushed, used_the_array_clause)."""

    # --- equality on a token-bearing field -------------------------------
    if isinstance(term, Binary) and term.op is BinaryOp.EQ:
        field, literal = _field_and_literal(term)
        if field is not None and literal is not None:
            cf = compiled.field(field.id)
            if cf and cf.eq_token_prefix:
                # Firestore allows ONE array-contains-any clause per query, so a
                # second equality term cannot also use the token array — it goes
                # to the residual rather than being silently dropped.
                if array_clause_used:
                    plan.note(
                        f"{field.id}: only one array-contains-any clause is allowed per query, "
                        "so this equality is post-filtered"
                    )
                    return False, False
                plan.filters.append(
                    StoreFilter(
                        path="eq",
                        op="array_contains_any",
                        value=[f"{cf.eq_token_prefix}={literal.value}"],
                    )
                )
                return True, True
            plan.note(f"{field.id}: not declared filterable, so no equality token exists")
            return False, False

    # --- range on a slot-bearing field -----------------------------------
    if isinstance(term, Binary) and term.op in _RANGE_OPS:
        field, literal = _field_and_literal(term)
        if field is not None and literal is not None:
            cf = compiled.field(field.id)
            if cf and cf.sort_slot:
                plan.filters.append(
                    StoreFilter(path=cf.sort_slot, op=_RANGE_OPS[term.op], value=literal.value)
                )
                return True, False
            plan.note(
                f"{field.id}: no typed sort slot assigned, so a range filter cannot be served "
                "by the store"
            )
            return False, False

    # --- membership: the PM-2a allow-list shape --------------------------
    if isinstance(term, In) and isinstance(term.value, FieldRef):
        cf = compiled.field(term.value.id)
        literals: list[Any] = []
        for option in term.options:
            if isinstance(option, Literal_):
                literals.append(option.value)
            elif isinstance(option, AllowListRef):
                # The whole reason PM-2a exists: an allow-list resolves to a
                # literal set at query time, so this shape is ALWAYS
                # push-downable where a general attribute expression is not.
                literals.extend(sorted(allow_lists.get(option.field, ())))
        if cf and cf.eq_token_prefix and literals:
            if array_clause_used:
                plan.note(f"{term.value.id}: array clause already used by another term")
                return False, False
            if len(literals) > 30:
                # Firestore caps the disjunction. A principal allow-list longer
                # than this is materialised differently rather than truncated —
                # truncating would silently narrow what a user can see.
                plan.note(
                    f"{term.value.id}: {len(literals)} options exceeds the 30-value "
                    "array-contains-any limit"
                )
                return False, False
            plan.filters.append(
                StoreFilter(
                    path="eq",
                    op="array_contains_any",
                    value=[f"{cf.eq_token_prefix}={v}" for v in literals],
                )
            )
            return True, True

    plan.note(f"{_describe(term)}: no store form")
    return False, False


def _field_and_literal(term: Binary) -> tuple[FieldRef | None, Literal_ | None]:
    """Normalise `field op literal` and `literal op field` to the same shape."""
    if isinstance(term.left, FieldRef) and isinstance(term.right, Literal_):
        return term.left, term.right
    if isinstance(term.right, FieldRef) and isinstance(term.left, Literal_):
        return term.right, term.left
    return None, None


def _describe(term: Expr) -> str:
    return getattr(term, "type", type(term).__name__)


def is_bounded(plan: QueryPlan) -> bool:
    """Whether the plan can be served without an unbounded scan.

    BP-26 refuses a permission rule whose evaluation would force fetch-then-
    filter over an unbounded result set: a rule that cannot be served is a rule
    that looks like it works until the register grows.
    """
    return bool(plan.filters) or plan.residual is None
