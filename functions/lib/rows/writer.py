"""``write_rows`` — THE row write path (BP-4).

Every channel is a **caller**, never a peer: grid edit, bulk paste, CSV import,
the admin API, undo, and later forms, automations, bound Sheets, MCP and inbound
webhooks. That is enforced by a fitness test, because "everything goes through
the writer" decays into "almost everything" within a quarter, and the resulting
defect class — "it validates in the grid but not on import" — lasts the life of
the product.

One transaction does all of it: validate, write the row, write the audit entry,
write the outbox envelope. Publish-after-commit is prohibited (see outbox.py).

**Writes are field-scoped, with a per-field version stamp.** GR-8 requires
last-write-wins per cell and forbids document-level locking, which a whole-row
save simply cannot express — two people editing different cells of one row would
lose one edit. PM-7's before/after delta and AU-8's field-level delta both
presuppose the writer knows which fields changed, so all three requirements
share this one mechanism.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lib.blueprint.compile import build_row_projection
from lib.permissions.model import Action, Decision
from lib.rows.audit import AuditClass, AuditEntry, diff
from lib.rows.outbox import DomainEvent, EventType, assert_no_row_bodies, build_envelope
from lib.rows.validate import ValidationOutcome, validate_write

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint

MAX_COMMIT_WRITES = 500
"""Firestore's cap. children + parent + 1 audit + 1 outbox <= 500, which is
where the 200-child product cap comes from with headroom for a wide child."""


class WriteRejected(Exception):
    def __init__(self, reason: str, *, outcome: ValidationOutcome | None = None, code: str = "invalid") -> None:
        self.reason = reason
        self.outcome = outcome
        self.code = code
        super().__init__(reason)


class WriteConflict(Exception):
    """Someone else changed the same CELL since this client read it.

    Carries the field ids and their current values so the client can show what
    it lost and offer to reapply — discarding the user's typing because a
    colleague edited a different part of the same row is the behaviour GR-8
    exists to prevent.
    """

    def __init__(self, fields: tuple[str, ...], current: dict[str, Any]) -> None:
        self.fields = fields
        self.current = current
        super().__init__("conflicting edit on: " + ", ".join(fields))


@dataclass(frozen=True, slots=True)
class WriteContext:
    workspace_id: str
    blueprint_id: str
    actor: str
    channel: str
    """grid | form | api | import | undo | automation | bound_sheet | system.

    Recorded on every audit entry. PM-7 requires the channel because "changed by
    Maya" and "changed by an automation Maya owns" are different facts.
    """

    correlation_id: str | None = None


@dataclass(slots=True)
class WriteResult:
    row_id: str
    created: bool
    values: dict[str, Any]
    changed_fields: tuple[str, ...]
    field_versions: dict[str, int]
    audit: AuditEntry
    events: tuple[DomainEvent, ...]
    rejected_fields: tuple[str, ...] = ()


@dataclass(slots=True)
class PendingWrite:
    """What one transaction will commit. Assembled, checked, then applied.

    Kept separate from the store call so the whole sequence — validation,
    versioning, audit, events — is unit-testable without an emulator.
    """

    row_path: tuple[str, ...]
    document: dict[str, Any]
    audit: AuditEntry
    envelope: Any
    child_writes: int = 0

    @property
    def commit_size(self) -> int:
        return 1 + self.child_writes + 2  # row + children + audit + outbox


def prepare_write(
    compiled: CompiledBlueprint,
    ctx: WriteContext,
    *,
    row_id: str | None,
    submitted_values: dict[str, Any],
    stored: dict[str, Any] | None,
    decision: Decision,
    child_count: int = 0,
    now: datetime | None = None,
) -> tuple[PendingWrite, WriteResult]:
    """Assemble one transactional write. Pure — no store access.

    Split out from the commit so every rule below is testable with no emulator
    and no network, which is what a single write path deserves.
    """
    now = now or datetime.now(UTC)
    is_create = stored is None

    required = Action.CREATE if is_create else Action.UPDATE
    if not decision.may(required):
        raise WriteRejected(
            f"not permitted to {required.value} this row",
            code="forbidden",
        )

    outcome = validate_write(
        compiled,
        submitted=submitted_values,
        stored=(stored or {}).get("values") if stored else None,
        decision=decision,
        is_create=is_create,
    )
    if outcome.rejected_fields:
        raise WriteRejected(
            "write includes fields you may not write: " + ", ".join(sorted(outcome.rejected_fields)),
            outcome=outcome,
            code="forbidden_fields",
        )
    if outcome.errors:
        raise WriteRejected("validation failed", outcome=outcome)

    previous_values: dict[str, Any] = (stored or {}).get("values", {})
    deltas = diff(previous_values, outcome.values)
    changed = tuple(d.field_id for d in deltas)

    if not is_create and not changed:
        raise WriteRejected("nothing changed", code="noop")

    # Per-field version stamps. Only bumped for fields that actually changed, so
    # a concurrent writer touching a different cell does not invalidate this one.
    versions: dict[str, int] = dict((stored or {}).get("fieldVersions", {}))
    for field_id in changed:
        versions[field_id] = versions.get(field_id, 0) + 1

    resolved_id = row_id or _new_row_id()
    document: dict[str, Any] = {
        "id": resolved_id,
        "values": outcome.values,
        "fieldVersions": versions,
        "blueprintId": compiled.id,
        "lastValidatedBlueprintVersion": compiled.version,
        "workspaceId": ctx.workspace_id,
        "updatedAt": now,
        "updatedBy": ctx.actor,
        # Reserved from P1 so no backfill is ever needed when BP-22 enforcement
        # arrives. Never enforced yet.
        "lifecycleStatus": (stored or {}).get("lifecycleStatus", "draft"),
        **build_row_projection(compiled, outcome.values),
    }
    if is_create:
        document["createdAt"] = now
        document["createdBy"] = ctx.actor
    else:
        document["createdAt"] = stored.get("createdAt", now)  # type: ignore[union-attr]
        document["createdBy"] = stored.get("createdBy", ctx.actor)  # type: ignore[union-attr]

    audit = AuditEntry(
        audit_class=AuditClass.CHANGE,
        action="row.create" if is_create else "row.update",
        actor=ctx.actor,
        channel=ctx.channel,
        correlation_id=ctx.correlation_id,
        workspace_id=ctx.workspace_id,
        blueprint_id=compiled.id,
        blueprint_version=compiled.version,
        row_id=resolved_id,
        deltas=deltas,
        at=now,
    )

    event = DomainEvent(
        event_type=EventType.ROW_CREATED if is_create else EventType.ROW_UPDATED,
        workspace_id=ctx.workspace_id,
        blueprint_id=compiled.id,
        blueprint_version=compiled.version,
        row_id=resolved_id,
        actor=ctx.actor,
        correlation_id=ctx.correlation_id,
        changed_fields=changed,
        at=now,
    )
    envelope = build_envelope([event])
    assert_no_row_bodies(envelope)

    pending = PendingWrite(
        row_path=(ctx.workspace_id, compiled.id, resolved_id),
        document=document,
        audit=audit,
        envelope=envelope,
        child_writes=child_count,
    )

    if pending.commit_size > MAX_COMMIT_WRITES:
        raise WriteRejected(
            f"this save needs {pending.commit_size} writes and a transaction allows "
            f"{MAX_COMMIT_WRITES}. Reduce the number of child rows saved at once.",
            code="commit_too_large",
        )

    result = WriteResult(
        row_id=resolved_id,
        created=is_create,
        values=outcome.values,
        changed_fields=changed,
        field_versions=versions,
        audit=audit,
        events=envelope.events,
    )
    return pending, result


def write_row(
    compiled: CompiledBlueprint,
    ctx: WriteContext,
    *,
    row_id: str | None,
    submitted_values: dict[str, Any],
    decision: Decision,
    submitted_versions: dict[str, int] | None = None,
    db: Any | None = None,
) -> WriteResult:
    """Commit one row write. The only function in Frame that writes a row.

    The read of the current row happens **inside** the transaction, so the
    version stamps this write is judged against are the ones it is written
    against. Reading first and then opening a transaction is the version of this
    function that passes every test and loses an edit in production.

    Row, audit entry and outbox envelope commit together or not at all. A
    committed row with no event is a permanently missing search document and a
    permanently wrong replica row; a committed event with no row is a consumer
    404 that retries forever.
    """
    from lib.firestore import run_in_transaction
    from lib.paths import audit_entry, outbox_envelope
    from lib.paths import row as row_path

    client = db if db is not None else _default_db()

    def body(txn: Any) -> WriteResult:
        stored: dict[str, Any] | None = None
        ref = None
        if row_id is not None:
            ref = row_path(client, ctx.workspace_id, compiled.id, row_id)
            snapshot = ref.get(transaction=txn)
            if not snapshot.exists:
                raise WriteRejected(f"row {row_id} does not exist", code="not_found")
            stored = snapshot.to_dict()

        pending, result = prepare_write(
            compiled,
            ctx,
            row_id=row_id,
            submitted_values=submitted_values,
            stored=stored,
            decision=decision,
            now=datetime.now(UTC),
        )

        conflicts = detect_conflicts(
            submitted_versions,
            (stored or {}).get("fieldVersions", {}),
            result.changed_fields,
        )
        if conflicts:
            current = {f: (stored or {}).get("values", {}).get(f) for f in conflicts}
            raise WriteConflict(conflicts, current)

        if ref is None:
            ref = row_path(client, ctx.workspace_id, compiled.id, result.row_id)

        # merge=True so a field-scoped write never blanks a field this writer
        # did not send. `document` already carries the restored values, so this
        # is belt and braces — but the belt is what protects a row when a future
        # caller forgets the braces.
        txn.set(ref, pending.document, merge=True)
        txn.set(
            audit_entry(client, ctx.workspace_id, uuid.uuid4().hex),
            pending.audit.to_document(),
        )
        txn.set(
            outbox_envelope(client, pending.envelope.envelope_id),
            pending.envelope.to_document(),
        )
        return result

    return run_in_transaction(body, db=client)


def commit_import(chunks: list[Any], ctx: WriteContext, blueprint_id: str, db: Any | None = None) -> int:
    """Commit prepared import chunks. Lives here because this is the only module
    allowed to touch row storage, and the fitness suite enforces that.

    The importer plans; this writes. Splitting them that way is what lets the
    whole of import validation be tested with no store at all, and it keeps the
    "every channel is a caller" rule true rather than aspirational — an importer
    that wrote rows itself would be the second write path by another name.

    Each chunk is its own transaction. A file larger than one transaction cannot
    be atomic against Firestore, so the honest design is chunks that each
    succeed or fail whole, with the count returned — not a promise of atomicity
    the store cannot keep.
    """
    from lib.firestore import run_in_transaction
    from lib.paths import audit_entry, outbox_envelope
    from lib.paths import row as row_path

    client = db if db is not None else _default_db()
    written = 0

    for chunk in chunks:
        def body(txn: Any, chunk: Any = chunk) -> int:
            for row_id, document in chunk.documents:
                txn.set(row_path(client, ctx.workspace_id, blueprint_id, row_id), document)
            txn.set(
                audit_entry(client, ctx.workspace_id, uuid.uuid4().hex),
                chunk.audit.to_document(),
            )
            txn.set(
                outbox_envelope(client, chunk.envelope.envelope_id),
                chunk.envelope.to_document(),
            )
            return len(chunk.documents)

        written += run_in_transaction(body, db=client)

    return written


def _default_db() -> Any:
    from lib.firestore import get_db

    return get_db()


def detect_conflicts(
    submitted_versions: dict[str, int] | None,
    stored_versions: dict[str, int],
    changed: tuple[str, ...],
) -> tuple[str, ...]:
    """Per-CELL conflict detection (GR-8).

    Two clients editing *different* cells of one row both succeed — which is the
    whole reason writes are field-scoped. Two editing the *same* cell: the later
    write wins and the loser is told which field it lost, so the client can offer
    the value back rather than silently discarding it.

    A submitted version of ``None`` means the client did not claim to know the
    current state, which is how an import or an automation writes.
    """
    if submitted_versions is None:
        return ()
    return tuple(
        field_id
        for field_id in changed
        if field_id in submitted_versions
        and submitted_versions[field_id] != stored_versions.get(field_id, 0)
    )


def _new_row_id() -> str:
    """Opaque, server-generated, never reused, never sequential.

    Sequential ids leak volume and creation order, and a timestamp id collides
    under concurrency. The human-readable identifier is a separate Blueprint-level
    declaration (BP-25) precisely so this one never has to carry meaning.
    """
    return uuid.uuid4().hex
