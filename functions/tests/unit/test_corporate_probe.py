"""The disclosure probe.

The probe gathers evidence; `classify` decides. What matters here is that the
evidence is gathered from the right layer, and that every failure to gather it
is recorded rather than swallowed — because a swallowed failure becomes a pass,
and a pass here is a cached label.
"""

from __future__ import annotations

from typing import Any

from lib.corporate.classify import classify
from lib.corporate.model import Dimension, Disclosure
from lib.corporate.probe import (
    ALL_STAFF_GROUP,
    BaseTable,
    all_staff_can_read,
    probe_catalogue,
    probe_relation,
    resolve_base_tables,
)

PROJECT = "unops-datahub"
CR = chr(13)
LF = chr(10)

# Verbatim from `unops-datahub.Dimensions_Api.Absence`, carriage returns and
# all. Copied rather than tidied: the CR-only line separator is the thing that
# broke the parser, and a cleaned-up constant would have hidden it.
REAL_VIEW = (
    "SELECT\r----------------------------------------------\r"
    "-- skip_auto_generate: false;               --\r"
    "----------------------------------------------\r"
    "\t\tAbsence\r\t\t , Absence_Description\r\t\t , System_Status\r"
    "\t\t , Last_Updated\r\t\t , Last_Updated_User \r\r"
    "FROM unops-datahub.Dimensions.Absence t"
)


def dimension(**over: Any) -> Dimension:
    return Dimension.model_validate({
        "id": "Dimensions_Api.Absence",
        "dataset": "Dimensions_Api",
        "table": "Absence",
        "label": "Absence",
        "business_key": "Absence",
        **over,
    })


# A sentinel, because `None` is a MEANING here — "the probe could not read
# this" — and a default of None would make "not supplied" and "explicitly
# unreadable" indistinguishable. That is the exact case the unreadable-evidence
# tests exist to exercise.
UNSET: Any = object()


class FakeInspector:
    def __init__(
        self,
        *,
        access: list[dict[str, Any]] | None = UNSET,
        definition: str | None = REAL_VIEW,
        tagged: tuple[str, ...] | None = (),
        policies: int | None = 0,
    ) -> None:
        self.access = (
            [{"role": "READER", "groupByEmail": ALL_STAFF_GROUP}]
            if access is UNSET
            else access
        )
        self.definition = definition
        self.tagged = tagged
        self.policies = policies
        self.asked_datasets: list[str] = []
        self.asked_tables: list[str] = []

    def dataset_access(self, project: str, dataset: str) -> list[dict[str, Any]] | None:
        self.asked_datasets.append(dataset)
        return self.access

    def view_definition(self, project: str, dataset: str, table: str) -> str | None:
        return self.definition

    def tagged_columns(self, project: str, dataset: str, table: str) -> tuple[str, ...] | None:
        self.asked_tables.append(f"{dataset}.{table}")
        return self.tagged

    def row_access_policy_count(self, project: str, dataset: str, table: str) -> int | None:
        return self.policies


def probe(**kw: Any) -> Any:
    return probe_relation(dimension(), FakeInspector(**kw), project=PROJECT)


# --- resolving a view to what it actually reads ---------------------------


def test_a_real_view_definition_resolves_to_its_base_table() -> None:
    assert resolve_base_tables(REAL_VIEW) == (
        BaseTable("unops-datahub", "Dimensions", "Absence"),
    )


def test_a_commented_out_table_reference_is_ignored() -> None:
    """A parse that read a comment as a FROM clause would probe the wrong table
    and report its policies as this view's."""
    definition = (
        "SELECT a -- FROM sneaky.dataset.table" + CR +
        "FROM unops-datahub.Dimensions.Absence t"
    )
    assert resolve_base_tables(definition) == (
        BaseTable("unops-datahub", "Dimensions", "Absence"),
    )


def test_the_line_separator_is_a_bare_carriage_return() -> None:
    """The published views contain no newline at all.

    A comment stripper anchored on a line-feed consumes the whole statement
    including its FROM clause, and nothing raises — the view resolves to
    nothing, the probe records a failed check, and every relation stays entitled
    for a reason that points at the view rather than at the parser.
    """
    assert LF not in REAL_VIEW
    assert CR in REAL_VIEW
    assert resolve_base_tables(REAL_VIEW)


def test_backticked_references_resolve() -> None:
    assert resolve_base_tables(
        "SELECT a FROM `unops-datahub`.`Dimensions`.`Absence`"
    ) == (BaseTable("unops-datahub", "Dimensions", "Absence"),)


def test_a_definition_that_cannot_be_parsed_yields_nothing() -> None:
    """Fails closed. "No base tables" is treated by the caller as a failed
    check, never as a view with no policies."""
    assert resolve_base_tables("SELECT 1") == ()
    assert resolve_base_tables(None) == ()
    assert resolve_base_tables("") == ()


def test_repeated_references_collapse() -> None:
    definition = (
        "SELECT a FROM unops-datahub.Dimensions.Absence t "
        "UNION ALL SELECT a FROM unops-datahub.Dimensions.Absence u"
    )
    assert len(resolve_base_tables(definition)) == 1


# --- check 1: dataset IAM -------------------------------------------------


def test_the_all_staff_group_holding_reader_passes_check_one() -> None:
    assert all_staff_can_read([{"role": "READER", "groupByEmail": ALL_STAFF_GROUP}]) is True


def test_a_different_group_does_not_pass_check_one() -> None:
    assert all_staff_can_read(
        [{"role": "READER", "groupByEmail": "g.bigquery.datahub.developers_level0@unops.org"}]
    ) is False


def test_a_role_that_does_not_confer_a_read_does_not_pass() -> None:
    """`bigquery.user` and `jobUser` permit running a job, not reading a table.
    Treating them as read access classifies a dimension open on the strength of
    a grant that grants nothing."""
    assert all_staff_can_read(
        [{"role": "roles/bigquery.user", "groupByEmail": ALL_STAFF_GROUP}]
    ) is False
    assert all_staff_can_read(
        [{"role": "roles/bigquery.jobUser", "groupByEmail": ALL_STAFF_GROUP}]
    ) is False


def test_unreadable_iam_is_a_failure_not_an_exception() -> None:
    """The probe gathers evidence; the classifier decides. Absence of evidence
    is failure."""
    assert all_staff_can_read(None) is False
    assert all_staff_can_read([]) is False


def test_an_iam_member_entry_is_matched_too() -> None:
    """Dataset access can be expressed as `iamMember: group:...` as well as
    `groupByEmail`, and a probe that read only one would miss a real grant."""
    assert all_staff_can_read(
        [{"role": "READER", "iamMember": f"group:{ALL_STAFF_GROUP}"}]
    ) is True


# --- asking the right layer -----------------------------------------------


def test_iam_is_asked_of_the_published_dataset_and_tags_of_the_base() -> None:
    """The split this design exists for. In `unops-datahub` the base
    `Dimensions` dataset carries the policy tags and grants no all-staff role,
    while `Dimensions_Api` carries no tags and does grant one. Asking either
    question of the wrong layer inverts the answer.
    """
    inspector = FakeInspector()
    probe_relation(dimension(), inspector, project=PROJECT)

    assert inspector.asked_datasets == ["Dimensions_Api"]
    assert inspector.asked_tables == ["Dimensions.Absence"]


def test_a_tagged_base_column_is_reported_even_though_the_view_is_untagged() -> None:
    """The case measured in the real warehouse: 85 tagged base columns,
    published through views that carry none."""
    result = probe(tagged=("Bank_Account_IBAN",))
    assert result.tagged_columns == ("Bank_Account_IBAN",)


# --- what the probe can and cannot answer today ---------------------------


def test_check_three_is_reported_as_unperformed_not_as_passed() -> None:
    """No floor principal is provisioned. Asserting a check that never ran is
    exactly what the classifier refuses to accept."""
    result = probe()

    assert result.floor_principal_sees_all_rows is False
    assert any("floor-principal" in e for e in result.probe_errors)


def test_nothing_reaches_open_while_check_three_cannot_run() -> None:
    """The correct and safe outcome, not a limitation to route around. Even a
    relation that passes every implementable check stays entitled."""
    result = probe()
    disclosure, reasons = classify(result)

    assert disclosure is Disclosure.ENTITLED
    assert any("floor principal" in r or "floor-principal" in r for r in reasons)


def test_every_failure_to_gather_evidence_is_recorded() -> None:
    """A swallowed failure becomes a pass, and a pass here is a cached label."""
    result = probe(access=None, tagged=None, policies=None)

    assert any("IAM" in e for e in result.probe_errors)
    assert any("policy tags" in e for e in result.probe_errors)
    assert any("row access policies" in e for e in result.probe_errors)


def test_an_unresolvable_view_reports_that_the_checks_ran_against_nothing() -> None:
    result = probe(definition="SELECT 1")

    assert result.base_tables_resolved is False
    assert any("base tables" in e for e in result.probe_errors)
    assert classify(result)[0] is Disclosure.ENTITLED


def test_row_access_policies_are_counted_across_every_base_table() -> None:
    result = probe(policies=2)
    assert result.row_access_policies == 2


# --- the whole catalogue --------------------------------------------------


def test_probing_a_catalogue_returns_one_probe_per_relation() -> None:
    relations = [dimension(), dimension(id="Dimensions_Api.Bank", table="Bank")]
    probes = probe_catalogue(relations, FakeInspector(), project=PROJECT)

    assert set(probes) == {"Dimensions_Api.Absence", "Dimensions_Api.Bank"}
    assert all(p.probe_errors for p in probes.values())
