"""Bulk import. A CALLER of the write path, never a second one.

This module is where BP-4's claim is either true or a comment. Every row an
import creates goes through the same validation, the same field-scoped version
stamps, the same audit entry and the same outbox envelope as a grid edit. The
defect class it exists to prevent — "it validates in the grid but not on
import" — is the single most common way a governed register acquires rows that
could not have been typed.

Three things an import needs that a single write does not:

**Its own verb.** ``Action.IMPORT`` is distinct from ``CREATE`` because bulk
creation bypasses the per-row attention create assumes. A team that may add
risks one at a time has not thereby been granted the right to paste in four
thousand.

**Partial success, reported per row.** All-or-nothing on a 5,000-row file means
one bad date costs the whole import, and the user's next move is to delete the
validation rather than fix the row. Per-row errors with line numbers are what
make a large import survivable.

**A bounded commit.** Firestore caps a transaction at 500 writes, and each row
costs itself plus its share of the audit and outbox documents, so rows are
committed in chunks with one audit entry and one envelope per chunk rather than
per row — otherwise a 5,000-row import writes 10,000 extra documents and the
activity drawer becomes unreadable.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lib.permissions.model import Action, Decision
from lib.rows.audit import AuditClass, AuditEntry
from lib.rows.outbox import DomainEvent, EventType, build_envelope
from lib.rows.validate import validate_write
from lib.rows.writer import WriteContext, WriteRejected

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint

CHUNK_ROWS = 400
"""Rows per transaction. 400 + 1 audit + 1 outbox leaves headroom under the
500-write cap for the index projection fields written alongside each row."""

MAX_IMPORT_ROWS = 20_000
"""Refused above this rather than attempted and abandoned half-way. A partially
applied import is the worst outcome: the user cannot tell which rows landed, and
re-running duplicates the ones that did."""


@dataclass(frozen=True, slots=True)
class RowError:
    line: int
    """1-based, counting the header — so it matches what the user sees in Excel.
    Reporting a 0-based index against a file the user is looking at is a small
    cruelty that turns a two-minute fix into a hunt."""

    field_id: str | None
    message: str
    code: str


@dataclass(slots=True)
class ImportPlan:
    """What an import would do, assembled before anything is written."""

    rows: list[dict[str, Any]] = dc_field(default_factory=list)
    errors: list[RowError] = dc_field(default_factory=list)
    unmapped_columns: list[str] = dc_field(default_factory=list)
    """Columns in the file that match no field.

    Reported rather than ignored: a mis-exported file whose columns silently
    vanish produces rows that look complete and are not.
    """

    total_lines: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def chunks(self) -> int:
        return (len(self.rows) + CHUNK_ROWS - 1) // CHUNK_ROWS


def parse_csv(text: str, compiled: CompiledBlueprint) -> tuple[list[dict[str, Any]], list[str], list[RowError]]:
    """Read a CSV into value maps keyed by FIELD ID.

    Columns are matched on field id first and then on label, because a file
    exported from Frame carries ids and a file typed by a human carries labels,
    and refusing the second would mean every import starts with a rename.
    """
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], [], [RowError(1, None, "The file is empty", "empty")]

    by_id = {fid: fid for fid in compiled.fields}
    by_label = {cf.definition.label.strip().lower(): fid for fid, cf in compiled.fields.items()}

    mapping: dict[int, str] = {}
    unmapped: list[str] = []
    for index, column in enumerate(header):
        key = column.strip()
        if key in by_id:
            mapping[index] = by_id[key]
        elif key.lower() in by_label:
            mapping[index] = by_label[key.lower()]
        elif key:
            unmapped.append(key)

    rows: list[dict[str, Any]] = []
    errors: list[RowError] = []
    for line_number, record in enumerate(reader, start=2):
        if not any(cell.strip() for cell in record):
            continue  # a blank line, not a blank row
        if len(rows) >= MAX_IMPORT_ROWS:
            errors.append(
                RowError(
                    line_number, None,
                    f"This file has more than {MAX_IMPORT_ROWS:,} rows. Split it and import "
                    "the parts — a half-applied import cannot be told from a finished one.",
                    "too_large",
                )
            )
            break
        values: dict[str, Any] = {}
        for index, cell in enumerate(record):
            field_id = mapping.get(index)
            if field_id is None:
                continue
            values[field_id] = _coerce(cell, compiled, field_id)
        rows.append(values)

    return rows, unmapped, errors


def _coerce(cell: str, compiled: CompiledBlueprint, field_id: str) -> Any:
    """Turn a CSV string into the field's storage type.

    A cell that cannot be coerced is left as the original string rather than
    replaced with ``None``: validation then reports "must be a number" against
    the value the user actually typed, which is a message they can act on.
    Silently nulling it produces "is required" against a cell that plainly is
    not empty.
    """
    text = cell.strip()
    if text == "":
        return None

    cf = compiled.field(field_id)
    if cf is None:
        return text

    match cf.storage:
        case "number":
            try:
                cleaned = text.replace(",", "").replace(" ", "")
                return float(cleaned) if "." in cleaned else int(cleaned)
            except ValueError:
                return text
        case "boolean":
            lowered = text.lower()
            if lowered in {"true", "yes", "y", "1"}:
                return True
            if lowered in {"false", "no", "n", "0"}:
                return False
            return text
        case "string_array":
            return [part.strip() for part in text.split(",") if part.strip()]
        case _:
            # A select field's LABEL is accepted as well as its key: a file a
            # human typed says "Open", not "open".
            if cf.definition.options:
                for option in cf.definition.options:
                    if text == option.key or text.lower() == option.label.strip().lower():
                        return option.key
            return text


def plan_import(
    text: str,
    compiled: CompiledBlueprint,
    decision: Decision,
) -> ImportPlan:
    """Validate every row before writing any of them.

    A dry run by construction: nothing here touches the store, so the caller can
    show the user exactly what will happen and what will not. An import that
    reports its failures only after writing half the file is one the user cannot
    safely retry.
    """
    plan = ImportPlan()

    if not decision.may(Action.IMPORT) and not decision.may(Action.CREATE):
        plan.errors.append(
            RowError(1, None, "You do not have permission to import into this register", "forbidden")
        )
        return plan

    rows, unmapped, errors = parse_csv(text, compiled)
    plan.unmapped_columns = unmapped
    plan.errors.extend(errors)
    plan.total_lines = len(rows)

    for offset, values in enumerate(rows):
        line = offset + 2  # header is line 1
        outcome = validate_write(
            compiled, submitted=values, stored=None, decision=decision, is_create=True
        )
        if outcome.rejected_fields:
            plan.errors.extend(
                RowError(line, field_id, "you may not write this field", "forbidden_field")
                for field_id in sorted(outcome.rejected_fields)
            )
            continue
        if outcome.errors:
            plan.errors.extend(
                RowError(line, e.field_id, e.message, e.code) for e in outcome.errors
            )
            continue
        plan.rows.append(outcome.values)

    return plan


@dataclass(slots=True)
class ImportChunk:
    """One transaction's worth: rows, one audit entry, one envelope."""

    documents: list[tuple[str, dict[str, Any]]]
    audit: AuditEntry
    envelope: Any

    @property
    def commit_size(self) -> int:
        return len(self.documents) + 2


def build_chunks(
    plan: ImportPlan, compiled: CompiledBlueprint, ctx: WriteContext, now: datetime | None = None
) -> list[ImportChunk]:
    """Assemble the transactions. Pure, so the whole shape is testable.

    One audit entry per chunk rather than per row, carrying the count. A 5,000
    row import that writes 5,000 change entries makes the activity drawer
    useless for exactly the register someone just changed most.
    """
    from lib.blueprint.compile import build_row_projection

    now = now or datetime.now(UTC)
    chunks: list[ImportChunk] = []

    for start in range(0, len(plan.rows), CHUNK_ROWS):
        batch = plan.rows[start : start + CHUNK_ROWS]
        documents: list[tuple[str, dict[str, Any]]] = []
        events: list[DomainEvent] = []

        for values in batch:
            row_id = uuid.uuid4().hex
            documents.append((
                row_id,
                {
                    "id": row_id,
                    "values": values,
                    "fieldVersions": {field_id: 1 for field_id in values},
                    "blueprintId": compiled.id,
                    "lastValidatedBlueprintVersion": compiled.version,
                    "workspaceId": ctx.workspace_id,
                    "lifecycleStatus": "draft",
                    "createdAt": now,
                    "createdBy": ctx.actor,
                    "updatedAt": now,
                    "updatedBy": ctx.actor,
                    **build_row_projection(compiled, values),
                },
            ))
            events.append(
                DomainEvent(
                    event_type=EventType.ROW_CREATED,
                    workspace_id=ctx.workspace_id,
                    blueprint_id=compiled.id,
                    blueprint_version=compiled.version,
                    row_id=row_id,
                    actor=ctx.actor,
                    correlation_id=ctx.correlation_id,
                    changed_fields=tuple(values),
                    at=now,
                )
            )

        chunk = ImportChunk(
            documents=documents,
            audit=AuditEntry(
                audit_class=AuditClass.CHANGE,
                action="row.import",
                actor=ctx.actor,
                channel=ctx.channel,
                correlation_id=ctx.correlation_id,
                workspace_id=ctx.workspace_id,
                blueprint_id=compiled.id,
                blueprint_version=compiled.version,
                # No deltas: every row is new, so a before/after per field would
                # be thousands of entries whose "before" is always empty.
                detail={"importedRows": len(batch), "chunk": len(chunks) + 1},
                at=now,
            ),
            envelope=build_envelope(events),
        )

        if chunk.commit_size > 500:
            raise WriteRejected(
                f"chunk of {chunk.commit_size} writes exceeds the transaction limit",
                code="commit_too_large",
            )
        chunks.append(chunk)

    return chunks
