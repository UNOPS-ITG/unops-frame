"""Resolving stored corporate references for a page (PRD 14).

Two rules carry the whole design, and both are asserted here rather than
described in a comment:

**One query per dimension per page, never one per row.** At BigQuery's
~300-400ms best case, per-row resolution is not slow, it is unusable — and
there is no warehouse-side fix, because query results are not cached for tables
under row-level security and BI Engine does not accelerate them at all.

**Frame caches no label anyone may be denied.** An entitled dimension renders
the label resolved in THIS reader's context, or a restricted stub. Never the
snapshot — a cached label on an entitled dimension is a quiet bypass of the
warehouse policy.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from lib.corporate.executor import Result
from lib.corporate.model import Attribute, ColumnRole, Dimension, Disclosure, RelationStatus, Source
from lib.corporate.resolve import (
    apply_resolution,
    plan_resolution,
    resolve_labels,
)


class _Field:
    def __init__(self, field_id: str, dimension: str | None) -> None:
        self.id = field_id
        self.dimension = dimension


class _Compiled:
    """Only what the resolver reads. A full CompiledBlueprint here would make
    the test about the compiler."""

    def __init__(self, fields: dict[str, tuple[str, str | None]]) -> None:
        self.fields = {
            fid: type("CF", (), {"storage": storage, "definition": _Field(fid, dim)})()
            for fid, (storage, dim) in fields.items()
        }


def _dimension(
    *,
    disclosure: Disclosure = Disclosure.ENTITLED,
    status: RelationStatus = RelationStatus.ACTIVE,
    business_key: str | None = "Agency_Code",
) -> Dimension:
    return Dimension(
        id="Dimensions_Api.Agency",
        dataset="Dimensions_Api",
        table="Agency",
        label="Agency",
        business_key=business_key,
        attributes=[
            Attribute(
                name="Agency_Code",
                label="Agency code",
                data_type="STRING",
                role=ColumnRole.DIMENSION,
                is_business_key=True,
            ),
            Attribute(
                name="Agency_Name",
                label="Agency name",
                data_type="STRING",
                role=ColumnRole.DIMENSION,
            ),
        ],
        disclosure=disclosure,
        label_visibility=disclosure,
        status=status,
    )


def _rows(count: int, *, key: str = "AG001") -> list[dict[str, Any]]:
    return [
        {
            "id": f"r{i}",
            "values": {
                "title": f"Row {i}",
                "agency": {
                    "key": key,
                    "label": "Cached name",
                    "snapshotAt": datetime.now(UTC).isoformat(),
                    "catalogueVersion": 1,
                },
            },
        }
        for i in range(count)
    ]


COMPILED = _Compiled(
    {"title": ("string", None), "agency": ("corporate_ref", "Dimensions_Api.Agency")}
)


# --- planning -------------------------------------------------------------


def test_two_hundred_rows_produce_one_query_not_two_hundred() -> None:
    """The rule the whole module exists for."""
    plan = plan_resolution(_rows(200), COMPILED)

    assert list(plan.by_dimension) == ["Dimensions_Api.Agency"]
    # One key, because every row references the same agency. The point is that
    # the plan is keyed by dimension rather than by row.
    assert plan.by_dimension["Dimensions_Api.Agency"] == {"AG001"}


def test_distinct_keys_are_deduplicated_across_the_page() -> None:
    rows = _rows(3, key="AG001") + _rows(3, key="AG002")
    plan = plan_resolution(rows, COMPILED)
    assert plan.by_dimension["Dimensions_Api.Agency"] == {"AG001", "AG002"}


def test_a_blueprint_with_no_corporate_fields_plans_nothing() -> None:
    """Almost every Blueprint. It must cost nothing — no store read, no query."""
    plan = plan_resolution(_rows(50), _Compiled({"title": ("string", None)}))
    assert plan.empty


def test_a_corporate_field_with_no_dimension_plans_nothing() -> None:
    """Declared as corporate data with no dimension chosen. There is nothing to
    search, and guessing one from the field id is the kind of inference that
    works until somebody names a field sensibly."""
    plan = plan_resolution(_rows(5), _Compiled({"agency": ("corporate_ref", None)}))
    assert plan.empty


def test_a_page_where_every_row_left_the_field_empty_plans_nothing() -> None:
    rows = [{"id": "r1", "values": {"title": "x"}}]
    assert plan_resolution(rows, COMPILED).empty


# --- rendering ------------------------------------------------------------


def test_an_open_dimension_renders_its_snapshot_without_any_query() -> None:
    rows = _rows(2)
    plan = plan_resolution(rows, COMPILED)
    dimension = _dimension(disclosure=Disclosure.OPEN)

    apply_resolution(rows, plan, {"Dimensions_Api.Agency": dimension}, {})

    for row in rows:
        assert row["values"]["agency"] == {
            "key": "AG001",
            "label": "Cached name",
            "state": "snapshot",
            "stale": False,
        }


def test_an_old_snapshot_is_marked_stale_rather_than_silently_shown() -> None:
    """A silently old label is worse than a visibly old one: the first time
    anyone notices otherwise is when two reports disagree."""
    rows = _rows(1)
    rows[0]["values"]["agency"]["snapshotAt"] = (
        datetime.now(UTC) - timedelta(days=200)
    ).isoformat()

    plan = plan_resolution(rows, COMPILED)
    apply_resolution(
        rows, plan, {"Dimensions_Api.Agency": _dimension(disclosure=Disclosure.OPEN)}, {}
    )

    assert rows[0]["values"]["agency"]["stale"] is True


def test_an_entitled_dimension_never_renders_the_cached_label() -> None:
    """The governing line: Frame caches no label anyone may be denied. An
    unresolvable key is a PM-5 stub, not the snapshot sitting in the row."""
    rows = _rows(1)
    plan = plan_resolution(rows, COMPILED)

    apply_resolution(rows, plan, {"Dimensions_Api.Agency": _dimension()}, {})

    assert rows[0]["values"]["agency"] == {"restricted": True}


def test_an_entitled_dimension_renders_the_label_resolved_for_this_reader() -> None:
    rows = _rows(1)
    plan = plan_resolution(rows, COMPILED)

    apply_resolution(
        rows,
        plan,
        {"Dimensions_Api.Agency": _dimension()},
        {"Dimensions_Api.Agency": {"AG001": "Their own view of it"}},
    )

    assert rows[0]["values"]["agency"] == {
        "key": "AG001",
        "label": "Their own view of it",
        "state": "resolved",
    }


def test_a_quarantined_relation_keeps_the_stored_value_and_marks_it() -> None:
    """Hiding it would make the row look empty rather than orphaned, and those
    call for different actions."""
    rows = _rows(1)
    plan = plan_resolution(rows, COMPILED)

    apply_resolution(
        rows,
        plan,
        {"Dimensions_Api.Agency": _dimension(status=RelationStatus.QUARANTINED)},
        {},
    )

    assert rows[0]["values"]["agency"]["state"] == "quarantined"
    assert rows[0]["values"]["agency"]["key"] == "AG001"


def test_a_relation_that_vanished_entirely_renders_as_orphaned() -> None:
    rows = _rows(1)
    plan = plan_resolution(rows, COMPILED)

    apply_resolution(rows, plan, {"Dimensions_Api.Agency": None}, {})

    assert rows[0]["values"]["agency"] == {
        "key": "AG001",
        "label": "AG001",
        "state": "orphaned",
    }


def test_a_field_level_restricted_stub_is_left_alone() -> None:
    """Field permission has already spoken. Re-deciding it here would be a
    second evaluator, which is the one thing PM-4 forbids."""
    rows = [{"id": "r1", "values": {"agency": {"restricted": True}}}]
    plan = plan_resolution(rows, COMPILED)

    apply_resolution(rows, plan, {"Dimensions_Api.Agency": _dimension()}, {})

    assert rows[0]["values"]["agency"] == {"restricted": True}


# --- fetching -------------------------------------------------------------


class _Client:
    def __init__(self, result: Result | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def run(self, query: Any, values: dict[str, Any], config: Any, credential: Any) -> Result:
        self.calls.append({"sql": query.sql, "values": values, "config": config})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


SOURCE = Source(id="datahub", project="unops-datahub", location="EU")
CREDENTIAL = object()


def test_the_query_batches_every_key_on_the_page_into_one_call() -> None:
    rows = _rows(3, key="AG001") + _rows(3, key="AG002") + _rows(3, key="AG003")
    plan = plan_resolution(rows, COMPILED)
    client = _Client(
        Result(rows=[{"Agency_Code": "AG001", "Agency_Name": "One"}])
    )

    resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension()},
        SOURCE,
        CREDENTIAL,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    assert len(client.calls) == 1, "nine rows, three keys, one query"
    assert client.calls[0]["values"] == {"keys": ["AG001", "AG002", "AG003"]}
    assert "IN UNNEST(@keys)" in client.calls[0]["sql"]


def test_an_open_dimension_is_never_queried() -> None:
    """Executing per user for data BigQuery has already ruled everyone may see
    is theatre: it costs latency and money to reach a known conclusion."""
    plan = plan_resolution(_rows(5), COMPILED)
    client = _Client(Result())

    resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension(disclosure=Disclosure.OPEN)},
        SOURCE,
        CREDENTIAL,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    assert client.calls == []


def test_no_credential_means_no_query_and_no_fallback_identity() -> None:
    """A missing consent is a missing credential, not a reason to read corporate
    data as somebody else."""
    plan = plan_resolution(_rows(5), COMPILED)
    client = _Client(Result())

    resolved = resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension()},
        SOURCE,
        None,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    assert resolved == {}
    assert client.calls == []


def test_a_warehouse_failure_degrades_to_stubs_rather_than_failing_the_page() -> None:
    """A register must survive a warehouse outage. The column says it does not
    know; every other column still works."""
    rows = _rows(2)
    plan = plan_resolution(rows, COMPILED)
    client = _Client(RuntimeError("BigQuery is unavailable"))

    resolved = resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension()},
        SOURCE,
        CREDENTIAL,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    assert resolved == {}
    apply_resolution(rows, plan, {"Dimensions_Api.Agency": _dimension()}, resolved)
    assert rows[0]["values"]["agency"] == {"restricted": True}


def test_the_job_carries_the_cost_controls_and_the_workspace_label() -> None:
    """Frame's own project submits and pays, so an unbounded scan is Frame's
    bill and an unlabelled one is a spend line nobody owns."""
    plan = plan_resolution(_rows(1), COMPILED)
    client = _Client(Result())

    resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension()},
        SOURCE,
        CREDENTIAL,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    config = client.calls[0]["config"]
    assert config.project == "frame-dev", "the BILLING project, not the warehouse"
    assert config.location == "EU"
    assert config.max_bytes_billed > 0
    assert config.labels()["workspace"] == "ws1"


def test_a_dimension_with_no_business_key_is_not_queried() -> None:
    """A lookup with no stable key stores a label, and a label is not an
    identity."""
    plan = plan_resolution(_rows(1), COMPILED)
    client = _Client(Result())

    resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension(business_key=None)},
        SOURCE,
        CREDENTIAL,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    assert client.calls == []


@pytest.mark.parametrize("status", [RelationStatus.QUARANTINED])
def test_a_quarantined_dimension_is_not_queried(status: RelationStatus) -> None:
    """It stops serving new resolutions immediately; stored values keep
    rendering, marked."""
    plan = plan_resolution(_rows(1), COMPILED)
    client = _Client(Result())

    resolve_labels(
        plan,
        {"Dimensions_Api.Agency": _dimension(status=status)},
        SOURCE,
        CREDENTIAL,
        billing_project="frame-dev",
        workspace_id="ws1",
        client=client,
    )

    assert client.calls == []
