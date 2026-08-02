"""Applying a Decision to a row, and counting honestly.

Four rules, each cheap now and expensive to retrofit because every renderer,
export and MCP response consumes the result:

**Withheld rows are absent from the array**, represented only in a count pair —
never phantom spacer rows. The two are different virtualization and pagination
contracts and cannot be swapped later.

**Withheld fields are present as typed stubs**, never an absent key, so no
renderer ever branches on key existence.

**Annotations are machine-readable objects**, never English strings, because
they have to render in six locales.

**Aggregates compute over the full set and say so.** Computing over the trimmed
set would mislead about totals; computing silently over the full set would leak
that hidden rows exist. Annotating resolves that by refusing the premise that
the gate must be invisible.
"""

from __future__ import annotations

from typing import Any

from lib.permissions.model import Annotation, Decision

RESTRICTED_STUB: dict[str, Any] = {"restricted": True}


def trim_row(row: dict[str, Any], decision: Decision) -> dict[str, Any] | None:
    """Return the row as this principal may see it, or ``None`` if withheld.

    ``None`` means "absent from the array but counted", which is what the caller
    turns into the withheld half of an annotation.
    """
    if not decision.visible:
        return None

    values = row.get("values", {})
    trimmed: dict[str, Any] = {}

    for field_id, value in values.items():
        if field_id in decision.readable_fields:
            trimmed[field_id] = value
        else:
            # Present, typed, and unmistakably withheld. Never omitted, never a
            # type default — a zero where a number was withheld is a lie that
            # then gets summed.
            trimmed[field_id] = dict(RESTRICTED_STUB)

    # A field the row has never been given a value for is still withheld if the
    # principal cannot read it, and a renderer needs to show the column stub.
    for field_id in decision.restricted_fields:
        trimmed.setdefault(field_id, dict(RESTRICTED_STUB))

    return {**{k: v for k, v in row.items() if k != "values"}, "values": trimmed}


def trim_page(
    rows: list[dict[str, Any]],
    decisions: list[Decision],
    *,
    scope: str = "page",
    certainty: str = "exact",
    ceiling: int | None = None,
) -> tuple[list[dict[str, Any]], Annotation, frozenset[str]]:
    """Trim a page and produce its annotation.

    Returns the visible rows, the count pair, and the set of fields withheld
    across *every* row in the page — which is GR-6's column-level stub, the case
    where a whole column renders as restricted rather than individual cells.
    """
    if len(rows) != len(decisions):
        raise ValueError("rows and decisions must correspond one to one")

    visible: list[dict[str, Any]] = []
    withheld = 0
    withheld_everywhere: set[str] | None = None

    for row, decision in zip(rows, decisions, strict=True):
        trimmed = trim_row(row, decision)
        if trimmed is None:
            withheld += 1
            continue
        visible.append(trimmed)
        # Intersection, not union: a column is a stub only if it was withheld on
        # every visible row. Withheld on some is per-cell, which PM-2 allows
        # because grants are scoped to field sets AND row conditions.
        if withheld_everywhere is None:
            withheld_everywhere = set(decision.restricted_fields)
        else:
            withheld_everywhere &= decision.restricted_fields

    annotation = Annotation(
        visible=len(visible),
        withheld=withheld,
        scope=scope,
        certainty=certainty,
        ceiling=ceiling,
    )
    return visible, annotation, frozenset(withheld_everywhere or ())


def annotate_aggregate(
    values: list[float],
    withheld_count: int,
    *,
    fn: str = "sum",
) -> dict[str, Any]:
    """An aggregate over the FULL set, carrying how many rows the reader cannot see.

    The honest answer to a genuine dilemma: computing over the trimmed set
    misleads about the total, computing silently over the full set leaks that
    hidden rows exist. Annotating declines the premise that the gate has to be
    invisible — and a visible gate stops two people arguing over different
    numbers without knowing why.
    """
    match fn:
        case "sum":
            value: float | None = sum(values)
        case "avg":
            value = (sum(values) / len(values)) if values else None
        case "min":
            value = min(values) if values else None
        case "max":
            value = max(values) if values else None
        case "count":
            value = len(values)
        case _:
            raise ValueError(f"unsupported aggregate {fn!r}")

    return {
        "fn": fn,
        "value": value,
        "annotation": {"computedOver": "full", "withheldRows": withheld_count},
    }
