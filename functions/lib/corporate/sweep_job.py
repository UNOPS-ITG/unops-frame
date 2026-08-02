"""The scheduled sweep: read the warehouse catalogue, write Frame's.

Runs on a schedule, not on demand. Browsing the catalogue would otherwise be the
most expensive thing in the product — three full metadata reads per page load,
against a warehouse, billed to Frame.

**It runs as a service identity, not as a user.** The catalogue is Frame's own
record and every workspace shares it; sweeping it as whoever happened to open a
page would make the contents depend on that person's entitlements, which is both
wrong and unstable. This is one of the non-interactive contexts PRD 14 names
explicitly: the claim is "Frame does not implement the policy", never "Frame is
never in possession of entitled data". The sweep reads *metadata* — table and
column names — and the identity it uses has visible, reviewable grants.

**Retirement is detected, never auto-remediated.** A relation that has vanished
upstream stops serving new picks immediately, and rows that already reference it
keep rendering with a staleness marker. Frame does not rewrite governed rows
from the warehouse: detection is instant and free, remediation is a scheduled
migration with a costed downstream cascade, and conflating the two changes a
total nobody decided to change.

The whole derivation is pure and lives in `sweep.py`. This module is the part
that talks to BigQuery and Firestore, and it is deliberately thin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from typing import Any, Protocol

from lib.corporate.catalogue_queries import (
    dictionary_query,
    relations_query,
    tables_query,
)
from lib.corporate.classify import Probe, classify_relation
from lib.corporate.executor import Credential, JobConfig
from lib.corporate.model import Disclosure, RelationStatus, Source
from lib.corporate.sweep import Catalogue, sweep

logger = logging.getLogger(__name__)

CATALOGUE_COLLECTION = "corporateCatalogue"
CURRENT = "current"


class MetadataReader(Protocol):
    """Runs a catalogue query and returns rows.

    A protocol so the job is testable end to end without BigQuery. The real
    implementation submits through the same executor as everything else, with
    the same ceiling, labels and timeout — the sweep is not exempt from the cost
    controls just because it reads metadata.
    """

    def read(self, sql: str, config: JobConfig, credential: Credential) -> list[dict[str, Any]]: ...


@dataclass(slots=True)
class SweepResult:
    source_id: str
    dimensions: int = 0
    facts: int = 0
    relations: int = 0
    open_dimensions: int = 0
    quarantined: list[str] = dc_field(default_factory=list)
    """Relations that were in the previous catalogue and are not in this one.

    Reported rather than silently dropped: each is a binding some Frame row may
    still reference, and the difference between "nobody noticed" and "an
    integrity panel raised it" is the whole value of sweeping on a schedule.
    """

    restored: list[str] = dc_field(default_factory=list)
    """Quarantined last time, present again now. A re-pointed view that came
    back is worth saying out loud — the alternative is a relation that silently
    starts serving picks again."""

    skipped: list[tuple[str, str]] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)
    swept_at: datetime | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def run_sweep(
    source: Source,
    reader: MetadataReader,
    credential: Credential,
    *,
    billing_project: str,
    previous: Catalogue | None = None,
    probes: dict[str, Probe] | None = None,
    now: datetime | None = None,
) -> tuple[Catalogue, SweepResult]:
    """One sweep. Returns the catalogue and what changed.

    Pure of Firestore — the caller persists. That keeps the comparison against
    the previous catalogue, which is the part with real consequences, testable
    without a store.
    """
    now = now or datetime.now(UTC)
    result = SweepResult(source_id=source.id, swept_at=now)

    config = JobConfig(
        project=billing_project,
        location=source.location,
        max_bytes_billed=source.max_bytes_billed,
        surface="catalogue-sweep",
    )

    try:
        dictionary = reader.read(dictionary_query(source.project, source.metadata_dataset).sql, config, credential)
        tables = reader.read(tables_query(source.project, source.metadata_dataset).sql, config, credential)
        relations = reader.read(relations_query(source.project, source.metadata_dataset).sql, config, credential)
    except Exception as exc:  # noqa: BLE001 - a failed sweep must not take the API with it
        logger.exception("Corporate-data sweep failed for source %s", source.id)
        result.errors.append(str(exc))
        # The PREVIOUS catalogue is returned unchanged. A failed sweep that
        # emptied the catalogue would quarantine every relation at once and
        # present as a mass retirement — the most alarming possible symptom of a
        # network error.
        return previous or Catalogue(), result

    catalogue = sweep(source, dictionary, tables, relations)

    _classify(catalogue, probes or {})
    _reconcile(catalogue, previous, result)

    result.dimensions = len(catalogue.dimensions)
    result.facts = len(catalogue.facts)
    result.relations = len(catalogue.relations)
    result.open_dimensions = sum(
        1 for d in catalogue.dimensions.values() if d.disclosure is Disclosure.OPEN
    )
    result.skipped = catalogue.skipped
    return catalogue, result


def _classify(catalogue: Catalogue, probes: dict[str, Probe]) -> None:
    """Assign disclosure from the probe results, defaulting to entitled.

    A relation with no probe is not open. That is the safe direction and it is
    also the honest one: an unprobed relation is one whose audience question has
    not been answered, and an unanswered question is not a negative answer.
    """
    for dimension in catalogue.dimensions.values():
        disclosure, reasons = classify_relation(dimension, probes.get(dimension.id, Probe()))
        dimension.disclosure = disclosure
        dimension.label_visibility = disclosure
        dimension.classification_reasons = reasons

    for fact in catalogue.facts.values():
        disclosure, reasons = classify_relation(fact, probes.get(fact.id, Probe()))
        fact.disclosure = disclosure
        fact.classification_reasons = reasons


def _reconcile(catalogue: Catalogue, previous: Catalogue | None, result: SweepResult) -> None:
    """Compare against the last sweep and mark what has moved.

    Quarantine, never deletion. A relation that vanished upstream is still
    referenced by rows that exist, and removing it from the catalogue would make
    those references orphaned rather than marked — the same end state with none
    of the explanation.
    """
    if previous is None:
        return

    seen = set(catalogue.dimensions) | set(catalogue.facts)
    known = set(previous.dimensions) | set(previous.facts)

    for missing in sorted(known - seen):
        stale = previous.dimensions.get(missing) or previous.facts.get(missing)
        if stale is None:
            continue
        quarantined = stale.model_copy(update={"status": RelationStatus.QUARANTINED})
        if missing in previous.dimensions:
            catalogue.dimensions[missing] = quarantined  # type: ignore[assignment]
        else:
            catalogue.facts[missing] = quarantined  # type: ignore[assignment]
        result.quarantined.append(missing)

    for returning in sorted(seen & known):
        was = previous.dimensions.get(returning) or previous.facts.get(returning)
        if was is not None and was.status is RelationStatus.QUARANTINED:
            result.restored.append(returning)


RELATIONS = "relations"

FIRESTORE_DOCUMENT_LIMIT = 1_048_576
"""1 MiB. The reason the catalogue is stored per relation rather than whole.

The real warehouse is ~960 relations and ~15,700 columns; as one document that
is roughly 12 MB, which exceeds both this limit and the 4 MiB gRPC message size.
Discovered by running the sweep against the real catalogue rather than the
fixture — a fixture of seven tables fits comfortably and proves nothing about
the thing it stands in for.
"""


def persist(
    db: Any,
    workspace_id: str,
    source: Source,
    catalogue: Catalogue,
    result: SweepResult,
) -> None:
    """Store the catalogue, one document per relation.

    Not one document for everything: the real warehouse does not fit, and the
    shape that does fit is also the shape the API wants — "list the bindable
    dimensions" becomes a query over documents rather than a load of the whole
    catalogue to filter in memory.

    Each relation carries its DERIVED form. A change to the sweep's logic
    therefore takes effect at the next sweep rather than immediately, which is
    the honest trade: the alternative — storing the raw rows and re-deriving on
    every read — costs a full re-derivation per page load, and the sweep is
    scheduled anyway.
    """
    from lib.paths import workspace

    root = workspace(db, workspace_id).collection(CATALOGUE_COLLECTION).document(CURRENT)
    relations = root.collection(RELATIONS)

    root.set(
        {
            "source": source.model_dump(mode="json"),
            "sweptAt": (result.swept_at or datetime.now(UTC)).isoformat(),
            "dimensionCount": result.dimensions,
            "factCount": result.facts,
            "relationCount": result.relations,
            "openDimensionCount": result.open_dimensions,
            "quarantined": result.quarantined,
            "restored": result.restored,
            "errors": result.errors,
        }
    )

    for dimension in catalogue.dimensions.values():
        relations.document(_document_id(dimension.id)).set(
            {"kind": "dimension", **dimension.model_dump(mode="json")}
        )
    for fact in catalogue.facts.values():
        relations.document(_document_id(fact.id)).set(
            {"kind": "fact", **fact.model_dump(mode="json")}
        )


def _document_id(relation_id: str) -> str:
    """`Dimensions_Api.Asset` -> `Dimensions_Api__Asset`.

    A Firestore document id may not contain a forward slash and is awkward with
    dots in a path; the relation id keeps its dot because it is what Frame rows
    store and changing that would orphan every reference.
    """
    return relation_id.replace(".", "__")


def load_catalogue(db: Any, workspace_id: str) -> Catalogue:
    """Read the stored catalogue back.

    Reads the derived documents directly — no re-derivation, and no warehouse
    call. That is the point of storing them this way.
    """
    from lib.corporate.model import Dimension, Fact
    from lib.paths import workspace

    catalogue = Catalogue()
    root = workspace(db, workspace_id).collection(CATALOGUE_COLLECTION).document(CURRENT)

    for snapshot in root.collection(RELATIONS).stream():
        data = snapshot.to_dict() or {}
        kind = data.pop("kind", "dimension")
        if kind == "fact":
            fact = Fact.model_validate(data)
            catalogue.facts[fact.id] = fact
        else:
            dimension = Dimension.model_validate(data)
            catalogue.dimensions[dimension.id] = dimension

    return catalogue


def audit_entry(result: SweepResult, actor: str, workspace_id: str) -> Any:
    """A GOVERNANCE audit entry, not a CHANGE one.

    The sweep changes what the whole workspace may bind to, and quarantining a
    relation can retire a field thousands of rows reference. That is a rule
    change in every sense that matters, and governance entries do not expire.
    """
    from lib.rows.audit import AuditClass, AuditEntry

    return AuditEntry(
        audit_class=AuditClass.GOVERNANCE,
        action="corporate.sweep",
        actor=actor,
        channel="system",
        correlation_id=None,
        workspace_id=workspace_id,
        blueprint_id=result.source_id,
        blueprint_version=0,
        detail={
            "dimensions": result.dimensions,
            "facts": result.facts,
            "relations": result.relations,
            "openDimensions": result.open_dimensions,
            "quarantined": result.quarantined,
            "restored": result.restored,
            "errors": result.errors,
        },
        at=result.swept_at or datetime.now(UTC),
    )
