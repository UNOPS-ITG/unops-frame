"""The conformance suite.

The assertion is **pushdown ∘ post-filter ≡ in-memory**, not backend ≡ backend.
Those are different claims and only the first is achievable: Firestore
legitimately excludes documents missing an inequality-filtered field and orders
strings by byte order, so demanding literal equality between the store predicate
and the evaluator would fail for exactly the cases that matter. What must hold
is that asking the store and then finishing in memory returns the same rows as
evaluating everything in memory.

**Each expression's pushdown classification is itself asserted.** A future
optimisation that wrongly marks a term push-downable would otherwise pass —
returning too few rows, silently, for whoever is most affected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from lib.blueprint.compile import compile_blueprint
from lib.blueprint.model import Blueprint, FieldDef, SelectOption, Tier, ViewDefaults
from lib.grammar.analyse import analyse, readback
from lib.grammar.ast import (
    Binary,
    BinaryOp,
    Call,
    FieldRef,
    FunctionName,
    In,
    IsEmpty,
    Literal_,
    Logical,
    LogicalOp,
    Not,
    ParentFieldRef,
    Scope,
    SubjectRef,
    parse,
)
from lib.grammar.compile_query import compile_query
from lib.grammar.evaluate import UNKNOWN, Context, ScopeViolation, evaluate, matches

# --- fixtures -------------------------------------------------------------

BP = Blueprint.model_validate(
    {
        "id": "risk",
        "name": "Risk Register",
        "workspace_id": "ws1",
        "tier": Tier.TEAM,
        "fields": [
            FieldDef(id="title", label="Title", type="text", variant="single", indexed=True),
            FieldDef(
                id="risk_type", label="Risk type", type="single_select", indexed=True,
                options=[SelectOption(key="conduct", label="Conduct"), SelectOption(key="fraud", label="Fraud")],
            ),
            FieldDef(id="amount", label="Amount", type="number", variant="decimal", indexed=True),
            FieldDef(id="due", label="Due date", type="date", indexed=True),
            # Deliberately NOT indexed: nothing about it can be pushed down.
            FieldDef(id="notes", label="Notes", type="text", variant="long"),
        ],
        "view_defaults": ViewDefaults(title_field="title"),
    }
)
COMPILED = compile_blueprint(BP)

ROWS: list[dict[str, Any]] = [
    {"title": "Alpha", "risk_type": "conduct", "amount": 150_000, "due": datetime(2026, 9, 1, tzinfo=UTC), "notes": "urgent"},
    {"title": "Beta", "risk_type": "fraud", "amount": 20_000, "due": datetime(2026, 7, 1, tzinfo=UTC), "notes": ""},
    {"title": "Gamma", "risk_type": "conduct", "amount": 90_000, "due": datetime(2027, 1, 1, tzinfo=UTC)},
    {"title": "Delta", "risk_type": "conduct", "notes": "no amount"},          # amount missing
    {"title": "Epsilon", "risk_type": "fraud", "amount": None, "due": None},   # explicit nulls
    {"title": "Zeta", "risk_type": "conduct", "amount": 150_000, "notes": {"restricted": True}},
]

CTX = Context(scope=Scope.ROW_PARENT_SUBJECT, now=datetime(2026, 8, 2, tzinfo=UTC))


def _ctx(row: dict[str, Any], **kw: Any) -> Context:
    return Context(row=row, scope=CTX.scope, now=CTX.now, **kw)


# --- the corpus -----------------------------------------------------------
# (id, expression, expected pushdown classification)

EQ_CONDUCT = Binary(op=BinaryOp.EQ, left=FieldRef(id="risk_type"), right=Literal_(value="conduct"))
GT_100K = Binary(op=BinaryOp.GT, left=FieldRef(id="amount"), right=Literal_(value=100_000))
NOTES_URGENT = Binary(op=BinaryOp.EQ, left=FieldRef(id="notes"), right=Literal_(value="urgent"))

CORPUS: list[tuple[str, Any, bool]] = [
    ("equality on an indexed select", EQ_CONDUCT, True),
    ("range on an indexed number", GT_100K, True),
    ("and of two pushable terms", Logical(op=LogicalOp.AND, operands=[EQ_CONDUCT, GT_100K]), True),
    ("membership on an indexed field", In(value=FieldRef(id="risk_type"), options=[Literal_(value="conduct"), Literal_(value="fraud")]), True),
    # --- must NOT be classified push-downable ---
    ("equality on an unindexed field", NOTES_URGENT, False),
    ("or across fields", Logical(op=LogicalOp.OR, operands=[EQ_CONDUCT, GT_100K]), False),
    ("negation", Not(operand=EQ_CONDUCT), False),
    ("is-empty", IsEmpty(operand=FieldRef(id="amount")), False),
    ("two equalities needing two array clauses", Logical(op=LogicalOp.AND, operands=[EQ_CONDUCT, Binary(op=BinaryOp.EQ, left=FieldRef(id="title"), right=Literal_(value="Alpha"))]), False),
    ("mixed pushable and residual", Logical(op=LogicalOp.AND, operands=[EQ_CONDUCT, NOTES_URGENT]), False),
    ("comparison against another field", Binary(op=BinaryOp.EQ, left=FieldRef(id="title"), right=FieldRef(id="notes")), False),
    ("date function", Binary(op=BinaryOp.LT, left=FieldRef(id="due"), right=Call(fn=FunctionName.TODAY)), False),
]


def _apply_store_filters(rows: list[dict[str, Any]], plan: Any) -> list[dict[str, Any]]:
    """A faithful-enough stand-in for what the store would return.

    Crucially it reproduces the behaviour that makes strict backend equality
    impossible: a document missing the filtered field is simply not returned by
    a range query, rather than being returned and evaluating to unknown.
    """
    out = []
    for row in rows:
        keep = True
        for f in plan.filters:
            if f.path == "eq":
                tokens = {
                    f"fld_{fid}={row[fid]}"
                    for fid in COMPILED.index_plan.eq_fields
                    if row.get(fid) is not None and not isinstance(row.get(fid), (dict, list))
                }
                if not (set(f.value) & tokens):
                    keep = False
                    break
            else:
                field_id = next(
                    (fid for fid, slot in COMPILED.index_plan.sort_slots.items() if slot == f.path), None
                )
                value = row.get(field_id) if field_id else None
                if value is None:  # absent from the index: not returned
                    keep = False
                    break
                try:
                    ok = {
                        "<": value < f.value, "<=": value <= f.value,
                        ">": value > f.value, ">=": value >= f.value,
                    }[f.op]
                except TypeError:
                    ok = False
                if not ok:
                    keep = False
                    break
        if keep:
            out.append(row)
    return out


@pytest.mark.parametrize("name,expr,expected_pushable", CORPUS, ids=[c[0] for c in CORPUS])
def test_pushdown_then_post_filter_equals_in_memory(
    name: str, expr: Any, expected_pushable: bool
) -> None:
    plan = compile_query(expr, COMPILED)

    # The classification is an asserted output, not an implementation detail.
    assert plan.fully_pushed is expected_pushable, (
        f"{name}: expected fully_pushed={expected_pushable}, got {plan.fully_pushed}. "
        f"Reasons: {plan.reasons}"
    )

    in_memory = [r for r in ROWS if matches(expr, _ctx(r))]
    combined = [
        r
        for r in _apply_store_filters(ROWS, plan)
        if plan.residual is None or matches(plan.residual, _ctx(r))
    ]

    assert [r["title"] for r in combined] == [r["title"] for r in in_memory], (
        f"{name}: store-plus-residual disagrees with the evaluator"
    )


def test_every_unpushed_term_carries_a_reason() -> None:
    """A term that quietly stays behind makes an unbounded scan look like a
    query. The query engine needs to be able to say so."""
    for name, expr, pushable in CORPUS:
        if pushable:
            continue
        plan = compile_query(expr, COMPILED)
        assert plan.reasons, f"{name}: no reason recorded for staying in the residual"


# --- null and unknown semantics ------------------------------------------


def test_missing_and_null_compare_as_unknown_not_false() -> None:
    row = {"title": "Delta"}  # amount absent entirely
    assert evaluate(GT_100K, _ctx(row)) is UNKNOWN
    assert evaluate(GT_100K, _ctx({"amount": None})) is UNKNOWN


def test_negation_of_unknown_stays_unknown() -> None:
    """The reason missing must not collapse to False: otherwise
    NOT (amount > 100000) would become true for a row with no amount."""
    assert evaluate(Not(operand=GT_100K), _ctx({"title": "Delta"})) is UNKNOWN


def test_three_valued_logic_follows_sql() -> None:
    unknown_term = GT_100K  # unknown on a row with no amount
    false_term = Binary(op=BinaryOp.EQ, left=FieldRef(id="risk_type"), right=Literal_(value="nope"))
    true_term = Binary(op=BinaryOp.EQ, left=FieldRef(id="risk_type"), right=Literal_(value="conduct"))
    row = {"risk_type": "conduct"}

    assert evaluate(Logical(op=LogicalOp.AND, operands=[unknown_term, false_term]), _ctx(row)) is False
    assert evaluate(Logical(op=LogicalOp.AND, operands=[unknown_term, true_term]), _ctx(row)) is UNKNOWN
    assert evaluate(Logical(op=LogicalOp.OR, operands=[unknown_term, true_term]), _ctx(row)) is True
    assert evaluate(Logical(op=LogicalOp.OR, operands=[unknown_term, false_term]), _ctx(row)) is UNKNOWN


def test_is_empty_can_see_missingness() -> None:
    """The one operator that inspects rather than propagates, which is what
    makes "this field is not filled in" expressible at all."""
    empty = IsEmpty(operand=FieldRef(id="amount"))
    assert evaluate(empty, _ctx({})) is True
    assert evaluate(empty, _ctx({"amount": None})) is True
    assert evaluate(empty, _ctx({"amount": 0})) is False


def test_a_restricted_stub_is_never_readable_as_data() -> None:
    """Branching on whether a field was withheld would leak precisely what the
    trim exists to hide."""
    row = {"notes": {"restricted": True}}
    assert evaluate(FieldRef(id="notes"), _ctx(row)) is UNKNOWN
    assert matches(NOTES_URGENT, _ctx(row)) is False


def test_strict_attributes_flips_the_unknown_default() -> None:
    """PM-2: by default an allow does not apply to a row with an unpopulated
    attribute. Frappe's equivalent defaults the other way, so a blank restricted
    field makes a row visible to everyone."""
    row = {"title": "Delta"}
    assert matches(GT_100K, _ctx(row)) is False
    assert matches(GT_100K, _ctx(row), unknown_matches=True) is True


def test_mismatched_types_are_unknown_not_false() -> None:
    """Silently False would make a permission rule quietly stop matching."""
    expr = Binary(op=BinaryOp.GT, left=FieldRef(id="title"), right=Literal_(value=5))
    assert evaluate(expr, _ctx({"title": "Alpha"})) is UNKNOWN


def test_division_by_zero_is_unknown_not_a_crash() -> None:
    expr = Binary(op=BinaryOp.DIV, left=Literal_(value=1), right=Literal_(value=0))
    assert evaluate(expr, _ctx({})) is UNKNOWN


def test_naive_datetimes_are_read_as_utc() -> None:
    """Reading a stored timestamp as local time is how a report silently shifts
    by hours depending on which machine ran it."""
    expr = Binary(op=BinaryOp.EQ, left=FieldRef(id="due"), right=Literal_(value=None))
    naive = _ctx({"due": datetime(2026, 9, 1)})
    aware = _ctx({"due": datetime(2026, 9, 1, tzinfo=UTC)})
    assert evaluate(FieldRef(id="due"), naive) == evaluate(FieldRef(id="due"), aware)
    assert evaluate(expr, naive) is UNKNOWN  # comparing to null is unknown, not false


# --- scope enforcement ----------------------------------------------------


def test_a_stored_value_may_not_read_its_parent() -> None:
    expr = ParentFieldRef(id="owner")
    with pytest.raises(ScopeViolation, match="row scope"):
        evaluate(expr, Context(row={}, scope=Scope.ROW))


def test_a_stored_value_may_not_read_the_acting_principal() -> None:
    """A materialised value that varies by reader is not a value."""
    expr = SubjectRef(attribute="email")
    with pytest.raises(ScopeViolation, match="permission rule"):
        evaluate(expr, Context(row={}, scope=Scope.ROW_PARENT))


def test_analysis_reports_the_narrowest_legal_scope() -> None:
    assert analyse(EQ_CONDUCT).required_scope is Scope.ROW
    assert analyse(ParentFieldRef(id="owner")).required_scope is Scope.ROW_PARENT
    assert analyse(SubjectRef(attribute="email")).required_scope is Scope.ROW_PARENT_SUBJECT


def test_analysis_finds_every_referenced_field() -> None:
    """Drives the child re-stamp fan-out, where being wrong is a silent
    permission leak."""
    expr = Logical(op=LogicalOp.AND, operands=[EQ_CONDUCT, GT_100K, ParentFieldRef(id="project")])
    result = analyse(expr)
    assert result.fields == {"risk_type", "amount"}
    assert result.parent_fields == {"project"}


# --- persistence and readback --------------------------------------------


def test_expressions_round_trip_through_json() -> None:
    """They are stored as AST, never as strings, so this is the persistence
    contract rather than a convenience."""
    expr = Logical(op=LogicalOp.AND, operands=[EQ_CONDUCT, GT_100K])
    assert parse(expr.model_dump(mode="json")) == expr


def test_unknown_node_types_are_rejected_not_ignored() -> None:
    """An expression that silently loses a clause evaluates to something
    plausible and wrong."""
    from lib.grammar.ast import ExpressionError

    with pytest.raises(ExpressionError):
        parse({"type": "exec", "cmd": "rm -rf /"})
    with pytest.raises(ExpressionError):
        parse({"type": "field", "id": "amount", "extra": "sneaky"})


def test_readback_renders_a_reviewable_sentence() -> None:
    labels = {"risk_type": "Risk type", "amount": "Amount"}
    expr = Logical(op=LogicalOp.AND, operands=[EQ_CONDUCT, GT_100K])
    assert readback(expr, labels) == "Risk type is conduct and Amount is more than 100,000"


def test_readback_brackets_a_nested_or() -> None:
    """"a and b or c" is genuinely ambiguous in English, and the whole point of
    the readback is that a steward can approve the meaning."""
    expr = Logical(
        op=LogicalOp.AND,
        operands=[EQ_CONDUCT, Logical(op=LogicalOp.OR, operands=[GT_100K, IsEmpty(operand=FieldRef(id="amount"))])],
    )
    said = readback(expr, {"risk_type": "Risk type", "amount": "Amount"})
    assert said == "Risk type is conduct and (Amount is more than 100,000 or Amount is empty)"


def test_readback_handles_subject_and_dates() -> None:
    expr = Binary(
        op=BinaryOp.LT,
        left=FieldRef(id="due"),
        right=Call(fn=FunctionName.DATEADD, args=[Call(fn=FunctionName.TODAY), Literal_(value=30)]),
    )
    assert readback(expr, {"due": "Due date"}) == "Due date is less than 30 days after today"
