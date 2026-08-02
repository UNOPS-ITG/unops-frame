"""The static analyser: what an expression reads, and what it says in English.

Two jobs that are cheap to do together because both are a tree walk.

**Referenced fields** drive three things that are not optional. The child
re-stamp fan-out denormalises exactly the parent fields any composed permission
rule reads, so PM-3 evaluation inside an embedded child grid needs no extra
reads — and a stale one there is a silent permission leak. BP-17's promotion
report counts rows with absent values per rule-referenced field. And BP-26
refuses an expression referencing a field that does not exist.

**The readback** is what makes a rule reviewable by the steward who has to
approve it, and it is the non-AI half of AI-2: the assistant generates an
expression, this renders it back in English, and the human confirms the meaning
rather than the syntax. Generated from the AST rather than remembered from the
user's input, so it describes what the rule *is* rather than what someone
believed they typed.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime
from typing import Any

from lib.grammar.ast import (
    AllowListRef,
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


@dataclass(slots=True)
class Analysis:
    fields: set[str] = dc_field(default_factory=set)
    parent_fields: set[str] = dc_field(default_factory=set)
    subject_attributes: set[str] = dc_field(default_factory=set)
    allow_lists: set[str] = dc_field(default_factory=set)
    functions: set[str] = dc_field(default_factory=set)
    max_depth: int = 0

    @property
    def required_scope(self) -> Scope:
        """The narrowest scope this expression can legally run at.

        BP-26 compares it against the scope the *slot* permits: a formula that
        reaches for the acting principal is refused at save rather than
        producing a stored value that differs per reader.
        """
        if self.subject_attributes or self.allow_lists:
            return Scope.ROW_PARENT_SUBJECT
        if self.parent_fields:
            return Scope.ROW_PARENT
        return Scope.ROW


def analyse(expr: Expr) -> Analysis:
    result = Analysis()
    _walk(expr, result, depth=1)
    return result


def _walk(node: Expr, out: Analysis, depth: int) -> None:
    out.max_depth = max(out.max_depth, depth)

    match node:
        case FieldRef():
            out.fields.add(node.id)
        case ParentFieldRef():
            out.parent_fields.add(node.id)
        case SubjectRef():
            out.subject_attributes.add(node.attribute)
        case AllowListRef():
            # Principal data, deliberately NOT a row field: reporting it as one
            # would make the child re-stamp fan-out denormalise a field that
            # does not exist on the parent.
            out.allow_lists.add(node.field)
        case Call():
            out.functions.add(node.fn.value)
            for arg in node.args:
                _walk(arg, out, depth + 1)
        case Binary():
            _walk(node.left, out, depth + 1)
            _walk(node.right, out, depth + 1)
        case Logical():
            for operand in node.operands:
                _walk(operand, out, depth + 1)
        case Not():
            _walk(node.operand, out, depth + 1)
        case IsEmpty():
            _walk(node.operand, out, depth + 1)
        case In():
            _walk(node.value, out, depth + 1)
            for option in node.options:
                _walk(option, out, depth + 1)
        case If():
            _walk(node.condition, out, depth + 1)
            _walk(node.then, out, depth + 1)
            _walk(node.otherwise, out, depth + 1)
        case Literal_():
            pass


# --- readback -------------------------------------------------------------

_COMPARISON_WORDS = {
    BinaryOp.EQ: "is",
    BinaryOp.NEQ: "is not",
    BinaryOp.LT: "is less than",
    BinaryOp.LTE: "is at most",
    BinaryOp.GT: "is more than",
    BinaryOp.GTE: "is at least",
}
_ARITHMETIC_WORDS = {
    BinaryOp.ADD: "plus",
    BinaryOp.SUB: "minus",
    BinaryOp.MUL: "times",
    BinaryOp.DIV: "divided by",
    BinaryOp.CONCAT: "followed by",
}


def readback(expr: Expr, labels: dict[str, str] | None = None) -> str:
    """Render an expression as a sentence.

    ``labels`` maps field ids to their human labels, so a steward reads "Risk
    type is Conduct" rather than "risk_type is conduct". Without it the field id
    is used, which is still far better than JSON.
    """
    return _say(expr, labels or {})


def _say(node: Expr, labels: dict[str, str]) -> str:
    match node:
        case Literal_():
            return _say_value(node.value)

        case FieldRef():
            return labels.get(node.id, node.id.replace("_", " "))

        case ParentFieldRef():
            label = labels.get(node.id, node.id.replace("_", " "))
            return f"the parent's {label}"

        case AllowListRef():
            label = labels.get(node.field, node.field.replace("_", " "))
            return f"the {label}s you are assigned to"

        case SubjectRef():
            return {
                "email": "the signed-in user's email",
                "subject": "the signed-in user",
                "groups": "the signed-in user's groups",
                "now": "the current time",
            }[node.attribute]

        case Binary() if node.op in _COMPARISON_WORDS:
            return f"{_say(node.left, labels)} {_COMPARISON_WORDS[node.op]} {_say(node.right, labels)}"

        case Binary():
            return f"{_say(node.left, labels)} {_ARITHMETIC_WORDS[node.op]} {_say(node.right, labels)}"

        case Logical():
            joiner = " and " if node.op is LogicalOp.AND else " or "
            parts = [_say(o, labels) for o in node.operands]
            # Bracket a nested OR inside an AND, since "a and b or c" is
            # genuinely ambiguous in English and the whole point is clarity.
            bracketed = [
                f"({p})" if isinstance(o, Logical) and o.op is not node.op else p
                for o, p in zip(node.operands, parts, strict=True)
            ]
            return joiner.join(bracketed)

        case Not():
            return f"not ({_say(node.operand, labels)})"

        case In():
            options = [_say(o, labels) for o in node.options]
            if len(options) == 1:
                return f"{_say(node.value, labels)} is {options[0]}"
            listed = ", ".join(options[:-1]) + f" or {options[-1]}"
            return f"{_say(node.value, labels)} is one of {listed}"

        case IsEmpty():
            return f"{_say(node.operand, labels)} is empty"

        case If():
            return (
                f"if {_say(node.condition, labels)} then {_say(node.then, labels)} "
                f"otherwise {_say(node.otherwise, labels)}"
            )

        case Call():
            match node.fn:
                case FunctionName.TODAY:
                    return "today"
                case FunctionName.NOW:
                    return "now"
                case FunctionName.DATEADD:
                    base, days = (_say(a, labels) for a in node.args)
                    return f"{days} days after {base}"

    return "an expression"


def _say_value(value: Any) -> str:
    if value is None:
        return "empty"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        # Quote only where it would otherwise read as part of the sentence.
        return f"“{value}”" if " " in value else value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:,}" if isinstance(value, int) else str(value)
