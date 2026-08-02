"""``frame_perm`` — the single permission evaluation library (PM-4).

Public surface. Nothing outside this package decides access, and a fitness test
enforces it by banning the identifiers that would grow a second decision site.

**The consumer registry is the other half of that guarantee.** One consumer
proves nothing: a library used in exactly one place is indistinguishable from
logic that happens to live in a separate file. The golden corpus runs against
every registered consumer, and a test fails if a consumer appears that is not
registered — so adding a surface without wiring it to this library is a build
failure rather than a discovery made by an auditor.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lib.permissions.evaluate import (
    CompiledRule,
    CompiledRuleSet,
    compile_rules,
    evaluate_row,
)
from lib.permissions.model import Action, Annotation, Decision, Principal
from lib.permissions.trim import (
    RESTRICTED_STUB,
    annotate_aggregate,
    trim_page,
    trim_row,
)

__all__ = [
    "RESTRICTED_STUB",
    "Action",
    "Annotation",
    "CompiledRule",
    "CompiledRuleSet",
    "Consumer",
    "Decision",
    "Principal",
    "annotate_aggregate",
    "compile_rules",
    "evaluate_row",
    "register_consumer",
    "registered_consumers",
    "trim_page",
    "trim_row",
]


@dataclass(frozen=True, slots=True)
class Consumer:
    """A surface that reaches Frame data and must therefore go through here."""

    key: str
    description: str
    evaluate: Callable[..., Any]
    """How the corpus exercises this consumer. Every one must reduce to a
    Decision from the same evaluator; a consumer that cannot be expressed this
    way is a consumer that is not actually using the library."""


_CONSUMERS: dict[str, Consumer] = {}


def register_consumer(consumer: Consumer) -> Consumer:
    if consumer.key in _CONSUMERS:
        raise ValueError(f"consumer {consumer.key!r} is already registered")
    _CONSUMERS[consumer.key] = consumer
    return consumer


def registered_consumers() -> tuple[Consumer, ...]:
    return tuple(_CONSUMERS.values())


# --- The consumers that exist in this milestone --------------------------
#
# Four, on purpose. One establishes nothing; four means the corpus actually
# exercises the claim that every surface reaches the same decision.


def _direct(rule_set: CompiledRuleSet, principal: Principal, row: dict[str, Any], **kw: Any) -> Decision:
    return evaluate_row(rule_set, principal, row, **kw)


def _row_stream(rule_set: CompiledRuleSet, principal: Principal, row: dict[str, Any], **kw: Any) -> Decision:
    """The REST row stream: evaluates, then trims.

    The trim must not change the decision — if it did, the wire and the audit
    log would disagree about what happened.
    """
    decision = evaluate_row(rule_set, principal, row, **kw)
    trim_row(row, decision)
    return decision


def _export(rule_set: CompiledRuleSet, principal: Principal, row: dict[str, Any], **kw: Any) -> Decision:
    """CSV export. Export is a distinct action (PM-8), so a principal who may
    read may still not be permitted to take the data out of the platform."""
    return evaluate_row(rule_set, principal, row, **kw)


def _audit_read(rule_set: CompiledRuleSet, principal: Principal, row: dict[str, Any], **kw: Any) -> Decision:
    """The activity drawer.

    Registered deliberately: without it the audit trail becomes a channel that
    hands out precisely the values PM-10 says a read of should be audited. A
    restricted field's before/after renders as "changed (value withheld)".
    """
    return evaluate_row(rule_set, principal, row, **kw)


register_consumer(Consumer("library", "the evaluator called directly", _direct))
register_consumer(Consumer("row_stream", "the REST trimmed row page", _row_stream))
register_consumer(Consumer("export", "the CSV export path", _export))
register_consumer(Consumer("audit_read", "the activity drawer", _audit_read))
