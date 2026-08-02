"""The shared expression AST.

Seven PRDs consume one grammar: formula fields (BP-9), conditional field
properties (BP-3a), permission row conditions (PM-2), automation conditions
(AU-1), form logic (FM-2), report and view filters (RP-1, GR-11), document
conditional blocks (DG-2) and field-qualified search terms (SR-3).

**Expressions persist as this AST, never as strings.** A string is an editor
affordance and a readback. With this many consumers, changing the grammar once
expressions are stored as text means a regex migration across user-authored
permission rules, saved-view filters, formula fields and form conditions
simultaneously — which is not a migration anybody performs correctly.

The node vocabulary is closed and small on purpose. Every expression language
grows a standard library, it is the fun part, and the vision names formula
complexity a top risk. Adding a function here is a code-first configuration
change with a review, not a steward setting, and the conformance suite makes the
cost visible across all three backends at once.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Scope(StrEnum):
    """Where an expression is allowed to read from.

    The rule that matters: **a value that is materialised, replicated or indexed
    may never be computed above ROW_PARENT.** A stored value that varies by
    reader is not a value, it is a bug with a schema — and it would be written
    once, by whoever happened to save the row, then served to everyone.
    """

    ROW = "row"
    ROW_PARENT = "row_parent"
    ROW_PARENT_SUBJECT = "row_parent_subject"


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Literal_(_Node):
    type: Literal["literal"] = "literal"
    value: str | int | float | bool | None


class FieldRef(_Node):
    type: Literal["field"] = "field"
    id: str


class ParentFieldRef(_Node):
    """One hop, and exactly one. PM-3 needs "visible to the parent's project
    manager"; anything deeper is a join, which belongs in a report."""

    type: Literal["parent_field"] = "parent_field"
    id: str


class SubjectRef(_Node):
    """The acting principal. Only legal at ROW_PARENT_SUBJECT scope, which is
    permission rules, view filters, automation conditions and search — never a
    stored value."""

    type: Literal["subject"] = "subject"
    attribute: Literal["email", "subject", "groups", "now"]


class BinaryOp(StrEnum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    CONCAT = "concat"


class Binary(_Node):
    type: Literal["binary"] = "binary"
    op: BinaryOp
    left: Expr
    right: Expr


class LogicalOp(StrEnum):
    AND = "and"
    OR = "or"


class Logical(_Node):
    type: Literal["logical"] = "logical"
    op: LogicalOp
    operands: list[Expr] = Field(min_length=2)


class Not(_Node):
    type: Literal["not"] = "not"
    operand: Expr


class In(_Node):
    type: Literal["in"] = "in"
    value: Expr
    options: list[Expr]


class IsEmpty(_Node):
    type: Literal["is_empty"] = "is_empty"
    operand: Expr


class If(_Node):
    type: Literal["if"] = "if"
    condition: Expr
    then: Expr
    otherwise: Expr


class FunctionName(StrEnum):
    TODAY = "today"
    NOW = "now"
    DATEADD = "dateadd"


class Call(_Node):
    """The closed function list. There are no user-defined functions, ever.

    Adding one is a platform change reviewed like any other, because each has to
    be implementable in all three backends and, where it can be pushed down, in
    the store's own query language too.
    """

    type: Literal["call"] = "call"
    fn: FunctionName
    args: list[Expr] = Field(default_factory=list)


Expr = Union[  # noqa: UP007 - pydantic discriminated unions need the explicit form
    Literal_,
    FieldRef,
    ParentFieldRef,
    SubjectRef,
    Binary,
    Logical,
    Not,
    In,
    IsEmpty,
    If,
    Call,
]

for _model in (Binary, Logical, Not, In, IsEmpty, If, Call):
    _model.model_rebuild()


class ExpressionError(ValueError):
    """A malformed expression. Carries a path so the editor can point at it."""

    def __init__(self, message: str, path: str = "$") -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


def parse(node: Any) -> Expr:
    """Validate raw JSON into the AST.

    Deliberately strict — unknown keys and unknown node types are errors, not
    things to ignore. An expression that silently loses a clause evaluates to
    something plausible and wrong, which is the worst outcome available for a
    permission rule.
    """
    from pydantic import TypeAdapter, ValidationError

    try:
        return TypeAdapter(Expr).validate_python(node)  # type: ignore[return-value]
    except ValidationError as exc:
        first = exc.errors()[0]
        path = "$" + "".join(f".{p}" if isinstance(p, str) else f"[{p}]" for p in first["loc"])
        raise ExpressionError(first["msg"], path) from exc


def dump(expr: Expr) -> dict[str, Any]:
    return expr.model_dump(mode="json")  # type: ignore[no-any-return]
