"""The discovery sweep and the disclosure classifier.

Run against metadata captured from `unops-datahub` — real table names, real
policy tags, the real relationship graph — because a fixture invented to match
the code proves the code matches the fixture. The capture deliberately includes
an open dimension, a policy-tagged dimension, a fact with measures and a heavily
tagged fact: a fixture containing only the easy cases tests only the easy cases.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import Any

import pytest

from lib.corporate.classify import (
    Probe,
    classify,
    classify_relation,
    label_visibility,
    tagged_columns,
)
from lib.corporate.model import ColumnRole, Disclosure, RelationStatus, Source
from lib.corporate.sweep import sweep

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "warehouse"


def load(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


SOURCE = Source(id="datahub", project="unops-datahub")


@pytest.fixture(scope="module")
def catalogue() -> Any:
    return sweep(SOURCE, load("dictionary"), load("tables"), load("relations"))


# --- discovery, not authoring --------------------------------------------


def test_the_catalogue_is_derived_from_warehouse_metadata_alone(catalogue: Any) -> None:
    """An admin registers a project and some exclusions. Everything below came
    from the data team's own catalogue — no registration queue, no steward
    turnaround, no hand-authored registry documents."""
    assert catalogue.dimensions
    assert catalogue.facts
    assert catalogue.relations


def test_dataset_membership_declares_dimension_versus_fact(catalogue: Any) -> None:
    assert all(d.dataset.endswith("Dimensions_Api") for d in catalogue.dimensions.values())
    assert all(f.dataset.endswith("Facts_Api") for f in catalogue.facts.values())


def test_a_relation_id_is_stable_and_not_derived_from_a_label(catalogue: Any) -> None:
    """Frame rows store this id. A label can be renamed upstream; an id keyed on
    one would silently orphan every row that referenced it."""
    for relation_id, dimension in catalogue.dimensions.items():
        assert relation_id == f"{dimension.dataset}.{dimension.table}"


def test_an_excluded_dataset_is_skipped_with_a_reason() -> None:
    """"Why can I not bind to this?" is a question an admin will ask about a
    table they can see in BigQuery. Silence makes it unanswerable."""
    excluded = Source(id="s", project="p", excluded_datasets=["Dimensions_Api"])
    result = sweep(excluded, load("dictionary"), load("tables"), load("relations"))

    assert result.dimensions == {}
    assert any("excluded" in reason for _, reason in result.skipped)


# --- what makes a relation bindable --------------------------------------


def test_a_dimension_without_a_business_key_is_not_bindable() -> None:
    """A lookup with no stable key stores a label, and a label is not an
    identity — renaming it upstream would orphan every row."""
    dictionary = [
        {**row, "Business_Key": "", "Business_Key_Flag": "NO"} for row in load("dictionary")
    ]
    tables = [{**row, "Business_Key": ""} for row in load("tables")]
    result = sweep(SOURCE, dictionary, tables, load("relations"))

    assert result.dimensions
    assert result.bindable_dimensions == []


def test_measures_are_the_declared_ones_not_every_numeric_column(catalogue: Any) -> None:
    """A year, a code and a count are all integers. Summing a year is the kind
    of wrong that survives review."""
    for fact in catalogue.facts.values():
        for measure in fact.measures:
            source = next(
                c for c in load("dictionary")
                if c["Table_Name"] == fact.table and c["Column_Name"] == measure.name
            )
            assert source["Column_Type"] == "MEASURE"


def test_a_facts_grain_comes_from_the_declared_relationship_graph(catalogue: Any) -> None:
    """This is what makes a corporate figure bindable to a Frame row. Without a
    declared grain there is no defensible answer to "which rows does this number
    belong to", and the honest response is to refuse the binding."""
    with_grain = [f for f in catalogue.facts.values() if f.grain]
    assert with_grain, "the captured graph should key at least one fact to a dimension"
    for fact in with_grain:
        assert all(dimension_id in catalogue.dimensions for dimension_id in fact.grain)


def test_a_fact_with_no_grain_is_not_bindable() -> None:
    result = sweep(SOURCE, load("dictionary"), load("tables"), [])
    assert result.facts
    assert all(not f.grain for f in result.facts.values())
    assert result.bindable_facts == []


def test_a_disabled_edge_is_kept_out_of_the_graph() -> None:
    """Filtered here rather than later: every consumer that forgot the filter
    would join on a relationship the data team has withdrawn."""
    relations = [{**r, "Enabled_Flag": "NO"} for r in load("relations")]
    result = sweep(SOURCE, load("dictionary"), load("tables"), relations)
    assert result.relations == []


# --- retirement -----------------------------------------------------------


def test_a_deleted_table_is_not_surfaced_at_all() -> None:
    """Not quarantined — gone. Quarantine is for a relation Frame rows still
    reference, and that decision belongs to reconciliation against stored
    values, not to the sweep."""
    tables = [{**t, "Table_Deleted_Flag": "YES"} for t in load("tables")]
    result = sweep(SOURCE, load("dictionary"), tables, load("relations"))
    assert result.dimensions == {}
    assert any("retired" in reason for _, reason in result.skipped)


def test_a_disabled_table_is_not_surfaced() -> None:
    tables = [{**t, "Enabled_Flag": "NO"} for t in load("tables")]
    result = sweep(SOURCE, load("dictionary"), tables, load("relations"))
    assert result.dimensions == {}


def test_a_surviving_relation_is_active(catalogue: Any) -> None:
    assert all(d.status is RelationStatus.ACTIVE for d in catalogue.dimensions.values())


# --- the disclosure classifier -------------------------------------------


PASSING = Probe(
    all_staff_can_read=True,
    row_access_policies=0,
    tagged_columns=(),
    floor_principal_sees_all_rows=True,
    frame_surface_is_wider=False,
    base_tables_resolved=True,
)


def test_all_four_checks_passing_is_the_only_route_to_open() -> None:
    disclosure, reasons = classify(PASSING)
    assert disclosure is Disclosure.OPEN
    assert reasons == ["all four disclosure checks passed"]


def test_a_probe_that_did_not_run_classifies_entitled() -> None:
    """Every field defaults to the unsafe answer, so a network timeout cannot
    become a disclosure. An unanswered audience question is not a negative
    answer."""
    disclosure, reasons = classify(Probe())
    assert disclosure is Disclosure.ENTITLED
    assert reasons


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("all_staff_can_read", False, "all-staff group"),
        ("row_access_policies", 1, "row access policy"),
        ("tagged_columns", ("Salary",), "policy tags"),
        ("floor_principal_sees_all_rows", False, "floor principal"),
        ("frame_surface_is_wider", True, "more widely"),
        ("base_tables_resolved", False, "base tables"),
    ],
)
def test_any_single_failure_forces_entitled(
    field: str, value: Any, expected_reason: str
) -> None:
    """Not a majority vote and not a score. Each check exists because no other
    one can see the thing it sees."""
    probe = dataclasses.replace(PASSING, **{field: value})
    disclosure, reasons = classify(probe)

    assert disclosure is Disclosure.ENTITLED
    assert any(expected_reason in r for r in reasons)


def test_a_probe_error_alone_forces_entitled() -> None:
    probe = dataclasses.replace(PASSING, probe_errors=("IAM read timed out",))
    assert classify(probe)[0] is Disclosure.ENTITLED


def test_a_tagged_column_beats_a_probe_that_forgot_to_look(catalogue: Any) -> None:
    """The column tags come from the catalogue, so a relation whose columns are
    tagged cannot be classified open by an incomplete probe."""
    tagged = [
        d for d in catalogue.dimensions.values() if tagged_columns(d)
    ] + [f for f in catalogue.facts.values() if tagged_columns(f)]
    assert tagged, "the fixture should contain at least one policy-tagged relation"

    disclosure, reasons = classify_relation(tagged[0], PASSING)
    assert disclosure is Disclosure.ENTITLED
    assert any("policy tags" in r for r in reasons)


def test_a_facts_tagged_non_measure_columns_force_entitled(catalogue: Any) -> None:
    """The gap that read a recruitment fact as open.

    A fact's sensitive columns are usually its grain keys and descriptive
    attributes — panel member names — not its measures, and the one numeric
    column on such a table is a harmless count. Classifying on measures alone
    said "open" about a table full of tagged personal data.
    """
    with_tagged_attributes = [
        f
        for f in catalogue.facts.values()
        if f.restricted_columns
        and not any(
            (m.policy_tag or "").strip() and not (m.policy_tag or "").startswith("Level 0")
            for m in f.measures
        )
    ]
    assert with_tagged_attributes, "the fixture should contain a fact tagged outside its measures"

    fact = with_tagged_attributes[0]
    disclosure, reasons = classify_relation(fact, PASSING)
    assert disclosure is Disclosure.ENTITLED
    assert any("policy tags" in r for r in reasons)


def test_an_untagged_relation_can_reach_open(catalogue: Any) -> None:
    open_ones = [d for d in catalogue.dimensions.values() if not tagged_columns(d)]
    assert open_ones, "the fixture should contain at least one fully open dimension"
    assert classify_relation(open_ones[0], PASSING)[0] is Disclosure.OPEN


def test_the_business_key_is_not_exempt_from_the_tag_check(catalogue: Any) -> None:
    """A project code that encodes geography discloses as surely as a name. A
    classifier that exempted keys because "it is only an identifier" would be
    wrong in exactly the cases that matter."""
    dimension = next(iter(catalogue.dimensions.values()))
    keyed = dimension.model_copy(
        update={
            "attributes": [
                a.model_copy(update={"policy_tag": "Level 3 Transactional"})
                if a.is_business_key
                else a
                for a in dimension.attributes
            ]
        }
    )
    if not any(a.is_business_key for a in dimension.attributes):
        pytest.skip("this fixture dimension declares no business-key column")

    assert classify_relation(keyed, PASSING)[0] is Disclosure.ENTITLED


def test_an_entitled_dimension_never_caches_its_label() -> None:
    """A cached label on an entitled dimension is a quiet bypass of the
    warehouse policy. Frame caches no label anyone may be denied."""
    from lib.corporate.model import Dimension

    dimension = Dimension(id="d.x", dataset="Dimensions_Api", table="X", label="X")
    assert label_visibility(dimension, Disclosure.ENTITLED) is Disclosure.ENTITLED
    assert label_visibility(dimension, Disclosure.OPEN) is Disclosure.OPEN


# --- what the real catalogue actually looks like --------------------------


def test_the_fixture_covers_the_cases_the_classifier_distinguishes(catalogue: Any) -> None:
    """Guards the fixture itself. If a future recapture loses the tagged rows,
    half of this file silently stops testing anything."""
    assert any(tagged_columns(d) for d in catalogue.dimensions.values()), "no tagged dimension"
    assert any(not tagged_columns(d) for d in catalogue.dimensions.values()), "no open dimension"
    assert any(f.measures for f in catalogue.facts.values()), "no fact with measures"
    assert any(
        a.role is ColumnRole.DIMENSION
        for d in catalogue.dimensions.values()
        for a in d.attributes
    ), "no declared dimension column"
