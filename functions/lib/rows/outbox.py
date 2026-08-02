"""The transactional outbox (AU-8).

The event is written **in the same transaction as the row**. Publish-after-commit
is prohibited, and the reason is not theoretical: search (SR-5 forbids
dual-write outright), notifications and the Postgres replica are all pure event
consumers, so a lost event is a permanently missing search document or a
permanently wrong replica row, and "reindexing is a replay" — SR-8's operational
promise — is only true if the log has no holes.

**One envelope document per transaction**, carrying a batch of events, rather
than one document per event. That keeps the commit arithmetic sane: Firestore
caps a commit at 500 writes, and the budget is

    children + parent + 1 audit entry + 1 outbox envelope <= 500

which is where the 200-child product cap comes from, with headroom.

Payloads carry **identifiers and deltas, never row bodies**. A consumer refetches
through the public API under its own identity, so the event stream can never
become a permission bypass with a subscription.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    ROW_CREATED = "frame.row.created"
    ROW_UPDATED = "frame.row.updated"
    ROW_DELETED = "frame.row.deleted"
    ROW_STATE_CHANGED = "frame.row.state_changed"
    CHILD_CREATED = "frame.child.created"
    CHILD_UPDATED = "frame.child.updated"
    CHILD_DELETED = "frame.child.deleted"
    BLUEPRINT_PUBLISHED = "frame.blueprint.published"
    """Required rather than optional: the projection re-tag sweep and PM-4's
    60-second propagation budget both need a rule-change trigger."""

    # Declared, unimplemented until their features land.
    ROW_SUBMITTED = "frame.row.submitted"
    ROW_CANCELLED = "frame.row.cancelled"
    ROW_AMENDED = "frame.row.amended"
    FORM_SUBMITTED = "frame.form.submitted"
    APPROVAL_DECIDED = "frame.approval.decided"


SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: EventType
    workspace_id: str
    blueprint_id: str
    blueprint_version: int
    row_id: str
    actor: str
    correlation_id: str | None
    changed_fields: tuple[str, ...] = ()
    """Field IDS, not values. A consumer that needs the value fetches it under
    its own identity."""

    detail: dict[str, Any] = dc_field(default_factory=dict)
    event_id: str = dc_field(default_factory=lambda: uuid.uuid4().hex)
    at: datetime = dc_field(default_factory=lambda: datetime.now(UTC))

    def to_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "schemaVersion": SCHEMA_VERSION,
            "type": self.event_type.value,
            "correlationId": self.correlation_id,
            "workspaceId": self.workspace_id,
            "blueprintId": self.blueprint_id,
            "blueprintVersion": self.blueprint_version,
            "rowId": self.row_id,
            "actor": self.actor,
            "changedFields": list(self.changed_fields),
            "detail": self.detail,
            "at": self.at,
        }


@dataclass(frozen=True, slots=True)
class OutboxEnvelope:
    """One document per transaction, holding the batch.

    The relay expands it into individual Pub/Sub messages with a dedupe key
    derived from the event id, so a relay that crashes mid-expansion redelivers
    rather than dropping.
    """

    envelope_id: str
    events: tuple[DomainEvent, ...]
    at: datetime = dc_field(default_factory=lambda: datetime.now(UTC))

    def to_document(self) -> dict[str, Any]:
        return {
            "envelopeId": self.envelope_id,
            "schemaVersion": SCHEMA_VERSION,
            "events": [e.to_payload() for e in self.events],
            "at": self.at,
            "published": False,
        }


def build_envelope(events: list[DomainEvent]) -> OutboxEnvelope:
    return OutboxEnvelope(envelope_id=uuid.uuid4().hex, events=tuple(events))


def assert_no_row_bodies(envelope: OutboxEnvelope) -> None:
    """AU-8 verbatim, asserted rather than trusted.

    A payload that carried trimmed row values would make the event stream a
    second, unevaluated read path — and one that is trimmed for whoever happened
    to write the row rather than for whoever consumes the event.
    """
    for event in envelope.events:
        payload = event.to_payload()
        if "values" in payload or "values" in payload.get("detail", {}):
            raise ValueError(
                f"event {event.event_type} carries row values. Events carry identifiers "
                "and deltas only; consumers refetch under their own identity."
            )
