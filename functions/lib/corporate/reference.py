"""What a row stores when a field points at corporate data.

    {key, label, snapshotAt, catalogueVersion}

Four fields, and each earns its place.

**`key`** is the identity, and the only part that is authoritative. Everything
else is a convenience that may go stale.

**`label`** is a snapshot, and it is what makes the whole feature affordable:
the grid filters, sorts, groups, exports, searches and generates documents
without touching BigQuery. A design that resolved labels on read would put a
300–400ms query on the path of every page — and there is no warehouse-side trick
that makes it faster, because query results are not cached for tables under
row-level security and BI Engine does not accelerate them.

**`snapshotAt`** is what makes staleness visible instead of invisible. Without
it a label from two years ago is indistinguishable from one taken this morning,
and the first time someone notices is when two reports disagree.

**`catalogueVersion`** ties the snapshot to the sweep that produced it, so a
relation that has since been quarantined can be found by the reconciliation pass
rather than by a user.

The rule that governs all of it: **Frame caches no label that anyone may be
denied.** On an `entitled` dimension the snapshot is not stored at all, and an
unresolvable key renders as a PM-5 restricted stub — because a cached label on
an entitled dimension is a quiet bypass of the warehouse policy, and a quiet one
is the worst kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lib.corporate.model import Dimension, Disclosure

STALE_AFTER_DAYS = 90
"""When a snapshot starts rendering with a staleness marker.

Not when it is refreshed — refreshing on read is the query-per-row this design
exists to avoid. The marker is honest about age; the refresh is a scheduled
sweep.
"""


@dataclass(frozen=True, slots=True)
class CorporateRef:
    key: str
    label: str | None = None
    snapshot_at: datetime | None = None
    catalogue_version: int = 0

    def to_value(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "snapshotAt": self.snapshot_at.isoformat() if self.snapshot_at else None,
            "catalogueVersion": self.catalogue_version,
        }

    def is_stale(self, now: datetime | None = None) -> bool:
        if self.snapshot_at is None:
            return True
        now = now or datetime.now(UTC)
        return (now - self.snapshot_at).days > STALE_AFTER_DAYS


class UnresolvableReference(ValueError):
    """A key that cannot be bound: the dimension is gone, quarantined, or has no
    business key. Refused on write rather than stored — a reference to nothing
    is a value that looks like data and is not."""


def make_reference(
    dimension: Dimension,
    key: str,
    label: str | None,
    *,
    catalogue_version: int,
    now: datetime | None = None,
) -> CorporateRef:
    """Build the stored value for one picked key.

    The label is dropped for an `entitled` dimension, whatever the caller
    supplied. That is deliberate and it is not defensive coding: the caller here
    is the picker, which resolved the label in the *picking user's* context, and
    storing it would make it visible to every later reader of the row — none of
    whom were checked.
    """
    if not dimension.bindable:
        raise UnresolvableReference(
            f"{dimension.id} cannot be referenced: "
            + ("it has been quarantined upstream" if dimension.status.value != "active"
               else "it declares no business key, so a stored reference would have no identity")
        )
    if not key:
        raise UnresolvableReference("a corporate reference needs a key")

    cache_label = dimension.label_visibility is Disclosure.OPEN
    return CorporateRef(
        key=key,
        label=label if cache_label else None,
        snapshot_at=(now or datetime.now(UTC)) if cache_label else None,
        catalogue_version=catalogue_version,
    )


def render(
    ref: CorporateRef,
    dimension: Dimension | None,
    *,
    resolved_label: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """What the grid shows for a stored reference.

    Four outcomes, and the distinction between the last two is the point:

    * an open dimension with a fresh snapshot renders the snapshot;
    * an open dimension with an old snapshot renders it *with a staleness
      marker*, because a silently old label is worse than a visibly old one;
    * an entitled dimension renders the label resolved in THIS reader's context,
      or a restricted stub if it could not be — never a cached one;
    * a quarantined dimension renders whatever is stored, marked, and does not
      offer to pick again.
    """
    if dimension is None:
        # The relation is gone entirely. The key is still shown, because it is
        # what the row actually contains and hiding it would make the row look
        # empty rather than orphaned.
        return {"key": ref.key, "label": ref.key, "state": "orphaned"}

    if dimension.status.value != "active":
        return {
            "key": ref.key,
            "label": ref.label or ref.key,
            "state": "quarantined",
            "stale": True,
        }

    if dimension.label_visibility is Disclosure.ENTITLED:
        if resolved_label is None:
            # A PM-5 restricted stub, not a blank and not the key: the key of an
            # entitled dimension can itself disclose — a project code encoding
            # geography discloses as surely as a name.
            return {"restricted": True}
        return {"key": ref.key, "label": resolved_label, "state": "resolved"}

    return {
        "key": ref.key,
        "label": ref.label or ref.key,
        "state": "snapshot",
        "stale": ref.is_stale(now),
    }


def from_value(value: Any) -> CorporateRef | None:
    """Parse a stored value. Tolerant of a bare key, which is what an import
    supplies — asking a spreadsheet to contain a four-field object would make
    import unusable for the field type most likely to be imported."""
    if isinstance(value, str):
        return CorporateRef(key=value)
    if not isinstance(value, dict) or not value.get("key"):
        return None

    snapshot_at = value.get("snapshotAt")
    parsed: datetime | None = None
    if isinstance(snapshot_at, str):
        try:
            parsed = datetime.fromisoformat(snapshot_at)
        except ValueError:
            parsed = None
    elif isinstance(snapshot_at, datetime):
        parsed = snapshot_at

    return CorporateRef(
        key=str(value["key"]),
        label=value.get("label"),
        snapshot_at=parsed,
        catalogue_version=int(value.get("catalogueVersion") or 0),
    )
