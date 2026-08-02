"""The only place Firestore paths are constructed.

Centralised because the layout carries two decisions that are easy to get wrong
by hand and expensive to fix afterwards.

**Paths alternate collection and document.** ``workspaces/{ws}/rows/{bp}/{row}``
is five segments and therefore names a *collection*, not a row — the PRD said
exactly that until it was corrected. The ``items`` segment is what makes it a
document path.

**Collection ids are fixed.** ``items`` and ``children`` are literals, and the
child's collection name is carried as a *field* (``collectionId``) rather than
being the collection's name. That means one collection-group index set covers
every Blueprint that will ever exist; a collection per named child collection
would multiply index definitions per Blueprint against a hard per-database cap.
"""

from __future__ import annotations

from typing import Any

WORKSPACES = "workspaces"
BLUEPRINTS = "blueprints"
BLUEPRINT_OVERLAYS = "blueprintOverlays"
ROWS = "rows"
ITEMS = "items"
CHILDREN = "children"
CATALOG = "catalog"
AUDIT = "audit"
OUTBOX = "outbox"
USERS = "users"
CONNECTORS = "connectors"
"""Per-principal connector grants, keyed on the stable SUBJECT.

Not the email, and not under a workspace. An address is mutable and
reassignable, so keying a credential that reads corporate data as its owner on
one means a renamed or recycled address inherits it. And a person's consent is
theirs, not a workspace's — they grant Frame access to *their* BigQuery, once,
for every workspace they work in.
"""


def workspace(db: Any, workspace_id: str) -> Any:
    return db.collection(WORKSPACES).document(workspace_id)


def blueprint(db: Any, workspace_id: str, blueprint_id: str) -> Any:
    return workspace(db, workspace_id).collection(BLUEPRINTS).document(blueprint_id)


def blueprint_overlay(db: Any, workspace_id: str, blueprint_id: str) -> Any:
    """A subscribing workspace's deviations from an upstream Blueprint (BP-19).

    An overlay, never a copy: there is one Blueprint document and the workspace
    stores only what it changed, so an upstream version bump applies to every
    subscriber with nothing to merge.
    """
    return workspace(db, workspace_id).collection(BLUEPRINT_OVERLAYS).document(blueprint_id)


def rows(db: Any, workspace_id: str, blueprint_id: str) -> Any:
    """The collection of row documents for one Blueprint."""
    return (
        workspace(db, workspace_id)
        .collection(ROWS)
        .document(blueprint_id)
        .collection(ITEMS)
    )


def row(db: Any, workspace_id: str, blueprint_id: str, row_id: str) -> Any:
    return rows(db, workspace_id, blueprint_id).document(row_id)


def children(db: Any, workspace_id: str, blueprint_id: str, row_id: str) -> Any:
    """Child rows of one parent, across every named child collection.

    Which collection a child belongs to is the ``collectionId`` field on the
    document, not this path — see the module docstring.
    """
    return row(db, workspace_id, blueprint_id, row_id).collection(CHILDREN)


def child(
    db: Any, workspace_id: str, blueprint_id: str, row_id: str, child_id: str
) -> Any:
    return children(db, workspace_id, blueprint_id, row_id).document(child_id)


def audit_entry(db: Any, workspace_id: str, entry_id: str) -> Any:
    """One audit stream per workspace, with a class discriminator on the document.

    One stream rather than four stores (PM-7): one write path, one query surface.
    Retention differs per class and is applied by a sweep reading that field, not
    by routing writes to different collections — a row's change history and the
    governance entry that changed its rules have to be readable together.
    """
    return workspace(db, workspace_id).collection(AUDIT).document(entry_id)


def outbox_envelope(db: Any, envelope_id: str) -> Any:
    """Database-level, not workspace-level.

    The relay tails one collection ordered by write time. Per-workspace outboxes
    would mean the relay either polls every workspace or maintains a discovery
    list, and either way the ordering guarantee it publishes with is per-shard
    rather than global.
    """
    return db.collection(OUTBOX).document(envelope_id)


def child_collection_group(db: Any) -> Any:
    """Every child row in the database, for BP-8's flat cross-parent queries.

    Callers must filter on ``workspaceId``, ``blueprintId`` and ``collectionId``
    — and the parent-permission ceiling still applies, evaluated per row by the
    permission library. A collection-group query is a way to *find* candidates,
    never a way to skip evaluation.
    """
    return db.collection_group(CHILDREN)
