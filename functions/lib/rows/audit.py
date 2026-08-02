"""Typed audit classes (PM-7).

One stream with a class discriminator — one write path, one query surface, not
four stores. Retention is declared per class, because a single unbounded log of
every write with a delta plus every restricted read, forever, is the first cost
line an audit function asks about and the first one that surprises operations.

The delta is **field-trimmed with the same Decision as everything else**. Without
that, the activity drawer becomes a channel that hands out precisely the values
PM-10 says a read of should be audited — a restricted field's before and after
renders as "changed (value withheld)".
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from lib.permissions.model import Decision

WITHHELD = "(value withheld)"


class AuditClass(StrEnum):
    CHANGE = "change"
    """Writes with a field-level before/after delta. What the activity drawer
    and the digest read. Retention follows the Blueprint's own policy and never
    expires before the rows it describes."""

    ACCESS = "access"
    """Reads of fields at or above the restricted threshold, exports, document
    generation, bound-Sheet refresh. Batched off the request path. Defaults to
    24 months."""

    GOVERNANCE = "governance"
    """Rule changes, Blueprint versions, promotion decisions, masking toggles,
    freeze, legal hold, naming-counter resets, service-principal rotation, and
    creation of any externally reachable surface. Exempt from retention and
    survives row deletion."""

    AUTH = "auth"
    """Sign-in, impersonation, service-principal use."""


# Days. GOVERNANCE is deliberately absent: it does not expire.
RETENTION_DAYS: dict[AuditClass, int | None] = {
    AuditClass.CHANGE: None,   # follows the Blueprint's retention policy
    AuditClass.ACCESS: 730,
    AuditClass.GOVERNANCE: None,
    AuditClass.AUTH: 365,
}


@dataclass(frozen=True, slots=True)
class FieldDelta:
    field_id: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class AuditEntry:
    audit_class: AuditClass
    action: str
    actor: str
    channel: str
    """How the identity was established — iap, dev-bypass, service. A bypassed
    request must never be indistinguishable downstream from a real session."""

    correlation_id: str | None
    workspace_id: str
    blueprint_id: str
    blueprint_version: int
    row_id: str | None = None
    deltas: tuple[FieldDelta, ...] = ()
    detail: dict[str, Any] = dc_field(default_factory=dict)
    at: datetime = dc_field(default_factory=lambda: datetime.now(UTC))

    def to_document(self) -> dict[str, Any]:
        return {
            "class": self.audit_class.value,
            "action": self.action,
            "actor": self.actor,
            "channel": self.channel,
            "correlationId": self.correlation_id,
            "workspaceId": self.workspace_id,
            "blueprintId": self.blueprint_id,
            "blueprintVersion": self.blueprint_version,
            "rowId": self.row_id,
            "deltas": [
                {"fieldId": d.field_id, "before": d.before, "after": d.after} for d in self.deltas
            ],
            "detail": self.detail,
            "at": self.at,
        }


def diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[FieldDelta, ...]:
    """Field-level delta. Both PM-7's before/after and AU-8's event payload
    presuppose the writer knows which fields changed, which is the same reason
    writes are field-scoped rather than whole-row."""
    changed: list[FieldDelta] = []
    for field_id in sorted(set(before) | set(after)):
        old, new = before.get(field_id), after.get(field_id)
        if old != new:
            changed.append(FieldDelta(field_id, old, new))
    return tuple(changed)


def trim_deltas(deltas: tuple[FieldDelta, ...], decision: Decision) -> tuple[FieldDelta, ...]:
    """Apply the reader's Decision to a change record.

    The audit-read path is a registered consumer of the permission library for
    exactly this reason.
    """
    return tuple(
        d
        if d.field_id in decision.readable_fields
        else FieldDelta(d.field_id, WITHHELD, WITHHELD)
        for d in deltas
    )
