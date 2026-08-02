"""The scheduled sweep.

The derivation is tested in `test_corporate_sweep.py`. What is left, and what
this file covers, is what happens when the warehouse changes underneath a
catalogue that Frame rows already reference — and what happens when the sweep
simply fails.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from lib.corporate.classify import Probe
from lib.corporate.executor import Credential, JobConfig
from lib.corporate.model import Disclosure, RelationStatus, Source
from lib.corporate.sweep import sweep
from lib.corporate.sweep_job import SweepResult, audit_entry, persist, run_sweep
from tests.fakes.firestore import FakeFirestore

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "warehouse"
SOURCE = Source(id="datahub", project="unops-datahub")
SERVICE = Credential(access_token="t", subject="sa-frame-sweep", is_service=True)


def load(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeReader:
    """Returns the fixture rows, in the order the job asks for them."""

    def __init__(self, *, fail: Exception | None = None, drop_tables: set[str] | None = None) -> None:
        self.fail = fail
        self.drop = drop_tables or set()
        self.configs: list[JobConfig] = []
        self.credentials: list[Credential] = []

    def read(self, sql: str, config: JobConfig, credential: Credential) -> list[dict[str, Any]]:
        if self.fail:
            raise self.fail
        self.configs.append(config)
        self.credentials.append(credential)

        if "Datahub_Data_Dictionary" in sql:
            rows = load("dictionary")
        elif "Datahub_Table_Reference" in sql:
            rows = load("relations")
        else:
            rows = load("tables")
        return [r for r in rows if r.get("Table_Name") not in self.drop]


def catalogue_of(drop: set[str] | None = None) -> Any:
    reader = FakeReader(drop_tables=drop)
    return sweep(
        SOURCE,
        reader.read("Datahub_Data_Dictionary", JobConfig(project="frame-local"), SERVICE),
        reader.read("Datahub_Table", JobConfig(project="frame-local"), SERVICE),
        reader.read("Datahub_Table_Reference", JobConfig(project="frame-local"), SERVICE),
    )


def run(**kw: Any) -> Any:
    return run_sweep(
        SOURCE,
        kw.pop("reader", FakeReader()),
        SERVICE,
        billing_project="frame-billing",
        **kw,
    )


# --- the happy path -------------------------------------------------------


def test_a_sweep_derives_the_catalogue_and_reports_what_it_found() -> None:
    catalogue, result = run()

    assert result.ok
    assert result.dimensions == len(catalogue.dimensions) > 0
    assert result.facts == len(catalogue.facts) > 0
    assert result.relations == len(catalogue.relations) > 0


def test_the_sweep_runs_as_a_service_identity() -> None:
    """The catalogue is Frame's own record and every workspace shares it.
    Sweeping as whoever opened a page would make its contents depend on that
    person's entitlements — wrong, and unstable."""
    reader = FakeReader()
    run(reader=reader)

    assert all(c.is_service for c in reader.credentials)


def test_the_sweep_is_not_exempt_from_the_cost_controls() -> None:
    """It reads metadata, not data. That exempts it from the four-template
    fence, not from the bill."""
    reader = FakeReader()
    run(reader=reader)

    assert all(c.max_bytes_billed == SOURCE.max_bytes_billed for c in reader.configs)
    assert all(c.surface == "catalogue-sweep" for c in reader.configs)
    assert all(c.project == "frame-billing" for c in reader.configs)


# --- classification -------------------------------------------------------


def test_an_unprobed_relation_is_not_open() -> None:
    """An unprobed relation is one whose audience question has not been
    answered, and an unanswered question is not a negative answer."""
    catalogue, _ = run()
    assert all(d.disclosure is Disclosure.ENTITLED for d in catalogue.dimensions.values())
    assert all(d.classification_reasons for d in catalogue.dimensions.values())


def test_a_relation_that_passes_every_check_becomes_open() -> None:
    catalogue, _ = run()
    untagged = next(
        d for d in catalogue.dimensions.values() if not any(not a.is_open for a in d.attributes)
    )
    passing = Probe(
        all_staff_can_read=True, row_access_policies=0, tagged_columns=(),
        floor_principal_sees_all_rows=True, frame_surface_is_wider=False,
        base_tables_resolved=True,
    )

    catalogue, result = run(probes={untagged.id: passing})

    assert catalogue.dimensions[untagged.id].disclosure is Disclosure.OPEN
    assert result.open_dimensions == 1


def test_an_entitled_dimension_never_gets_open_label_visibility() -> None:
    """A cached label on an entitled dimension is a quiet bypass of the
    warehouse policy."""
    catalogue, _ = run()
    for dimension in catalogue.dimensions.values():
        if dimension.disclosure is Disclosure.ENTITLED:
            assert dimension.label_visibility is Disclosure.ENTITLED


# --- reconciliation -------------------------------------------------------


def test_a_relation_that_vanished_upstream_is_quarantined_not_deleted() -> None:
    """It is still referenced by rows that exist. Removing it from the catalogue
    would make those references orphaned rather than marked — the same end state
    with none of the explanation."""
    before = catalogue_of()
    gone = next(iter(before.dimensions))
    table = before.dimensions[gone].table

    catalogue, result = run(reader=FakeReader(drop_tables={table}), previous=before)

    assert gone in result.quarantined
    assert catalogue.dimensions[gone].status is RelationStatus.QUARANTINED


def test_a_quarantined_relation_is_no_longer_bindable() -> None:
    """It stops serving new picks immediately. Existing rows keep rendering."""
    before = catalogue_of()
    gone = next(iter(before.dimensions))
    table = before.dimensions[gone].table

    catalogue, _ = run(reader=FakeReader(drop_tables={table}), previous=before)

    assert catalogue.dimensions[gone].bindable is False
    assert gone not in {d.id for d in catalogue.bindable_dimensions}


def test_a_relation_that_came_back_is_reported() -> None:
    """A re-pointed view returning is worth saying out loud — the alternative is
    a relation that silently starts serving picks again."""
    full = catalogue_of()
    gone = next(iter(full.dimensions))
    table = full.dimensions[gone].table

    quarantined, _ = run(reader=FakeReader(drop_tables={table}), previous=full)
    _, result = run(previous=quarantined)

    assert gone in result.restored
    assert result.quarantined == []


def test_a_first_sweep_quarantines_nothing() -> None:
    _, result = run(previous=None)
    assert result.quarantined == []
    assert result.restored == []


# --- failure --------------------------------------------------------------


def test_a_failed_sweep_leaves_the_previous_catalogue_untouched() -> None:
    """A sweep that emptied the catalogue on failure would quarantine every
    relation at once and present as a mass retirement — the most alarming
    possible symptom of a network error."""
    before = catalogue_of()

    catalogue, result = run(reader=FakeReader(fail=RuntimeError("BigQuery unreachable")), previous=before)

    assert not result.ok
    assert result.errors
    assert catalogue is before
    assert result.quarantined == []


def test_a_failed_first_sweep_yields_an_empty_catalogue_rather_than_raising() -> None:
    """A failed sweep must not take the API with it — the register still works
    without corporate data."""
    catalogue, result = run(reader=FakeReader(fail=RuntimeError("boom")), previous=None)

    assert catalogue.dimensions == {}
    assert not result.ok


# --- persistence and audit ------------------------------------------------


def test_the_catalogue_is_stored_one_document_per_relation() -> None:
    """The whole catalogue does not fit in one Firestore document.

    The real warehouse is ~960 relations and ~15,700 columns, which as a single
    document is roughly 12 MB against a 1 MiB limit — and it failed on the 4 MiB
    gRPC message size first. Found by running the sweep against the real
    catalogue: a fixture of seven tables fits comfortably and proves nothing
    about the thing it stands in for.

    The shape that fits is also the shape the API wants: "list the bindable
    dimensions" is a query over documents rather than a load of everything.
    """
    db = FakeFirestore()
    catalogue, result = run()
    persist(db, "ws1", SOURCE, catalogue, result)

    root = db.docs["workspaces/ws1/corporateCatalogue/current"]
    assert root["dimensionCount"] == result.dimensions
    assert "dictionary" not in root, "the raw metadata is what did not fit"

    documents = db.paths_under("workspaces/ws1/corporateCatalogue/current/relations/")
    assert len(documents) == result.dimensions + result.facts


def test_a_stored_catalogue_reads_back_identically() -> None:
    """The derived form is stored, so a read needs no re-derivation and no
    warehouse call — which is the point of storing it this way."""
    from lib.corporate.sweep_job import load_catalogue

    db = FakeFirestore()
    catalogue, result = run()
    persist(db, "ws1", SOURCE, catalogue, result)

    restored = load_catalogue(db, "ws1")

    assert set(restored.dimensions) == set(catalogue.dimensions)
    assert set(restored.facts) == set(catalogue.facts)
    for relation_id, dimension in catalogue.dimensions.items():
        assert restored.dimensions[relation_id].business_key == dimension.business_key
        assert restored.dimensions[relation_id].disclosure is dimension.disclosure
    for relation_id, fact in catalogue.facts.items():
        assert restored.facts[relation_id].grain == fact.grain


def test_a_relation_id_survives_the_document_id_it_is_stored_under() -> None:
    """A Firestore document id cannot contain a slash and is awkward with dots.
    The relation id keeps its dot regardless, because it is what Frame rows
    store — changing it would orphan every reference."""
    db = FakeFirestore()
    catalogue, result = run()
    persist(db, "ws1", SOURCE, catalogue, result)

    from lib.corporate.sweep_job import load_catalogue

    assert all("." in relation_id for relation_id in load_catalogue(db, "ws1").dimensions)


def test_the_sweep_writes_a_governance_audit_entry() -> None:
    """It changes what the whole workspace may bind to, and quarantining a
    relation can retire a field thousands of rows reference. Governance entries
    do not expire."""
    _, result = run()
    entry = audit_entry(result, actor="sa-frame-sweep", workspace_id="ws1")

    assert entry.audit_class.value == "governance"
    assert entry.action == "corporate.sweep"
    assert entry.channel == "system"
    assert entry.detail["dimensions"] == result.dimensions


def test_the_audit_entry_names_what_was_quarantined() -> None:
    before = catalogue_of()
    gone = next(iter(before.dimensions))
    _, result = run(
        reader=FakeReader(drop_tables={before.dimensions[gone].table}), previous=before
    )

    entry = audit_entry(result, actor="sa", workspace_id="ws1")
    assert gone in entry.detail["quarantined"]


def test_a_result_with_no_errors_is_ok() -> None:
    assert SweepResult(source_id="s").ok is True
    assert SweepResult(source_id="s", errors=["x"]).ok is False
