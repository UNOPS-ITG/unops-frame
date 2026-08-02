"""The four templates, and the fence around them.

"Frame never aggregates" is either a mechanism or a sentence in a document. This
file is the mechanism.
"""

from __future__ import annotations

import pytest

from lib.corporate.sql import (
    TEMPLATES,
    AggregationAttempted,
    UnsafeIdentifier,
    assert_no_aggregation,
    fact_measures_at_grain,
    ident,
    lookup_by_key,
    lookup_by_keys,
    search_labels,
)

P, D, T = "unops-datahub", "Dimensions_Api", "Asset"


# --- the fence ------------------------------------------------------------


def test_there_are_exactly_four_templates() -> None:
    """A fifth is a design decision, not a patch. Without this the fence is a
    comment: someone adds a template that aggregates and the other tests keep
    passing because they only look at the four they know about."""
    assert len(TEMPLATES) == 4


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SUM(amount) FROM t",
        "SELECT a FROM t GROUP BY a",
        "SELECT a FROM t JOIN u ON t.a = u.a",
        "SELECT ROW_NUMBER() OVER (ORDER BY a) FROM t",
        "SELECT COUNT(*) FROM t",
        "SELECT ARRAY_AGG(x) FROM t",
        "SELECT a FROM t UNION ALL SELECT a FROM u",
    ],
)
def test_the_fence_refuses_every_shape_of_aggregation(sql: str) -> None:
    """If a number does not exist at a grain, that is a mart request to the data
    platform team — they own the definition of "expenditure to date" and Frame
    does not."""
    with pytest.raises(AggregationAttempted):
        assert_no_aggregation(sql)


def test_every_template_passes_its_own_fence() -> None:
    """Constructed rather than asserted: `Query.__post_init__` runs the check, so
    a template that aggregated could not be built at all."""
    lookup_by_key(P, D, T, "Asset", ["Asset", "Asset_Description"])
    lookup_by_keys(P, D, T, "Asset", ["Asset"])
    search_labels(P, D, T, "Asset", "Asset_Description")
    fact_measures_at_grain(P, "Facts_Api", "Asset_Transactions", ["Asset"], ["Amount"])


# --- identifiers are the security boundary --------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "Asset; DROP TABLE x",
        "Asset`",
        "Dimensions_Api.Asset",   # a dot would let a name escape its dataset
        "",
        "1_starts_with_a_digit",
        "a" * 200,
        "Asset OR 1=1",
        "Asset--",
    ],
)
def test_an_identifier_that_is_not_plainly_an_identifier_is_refused(bad: str) -> None:
    """The catalogue is swept from a system Frame does not control, and a table
    name is exactly the value that is trusted until someone can influence it.
    Identifiers cannot be parameterised in BigQuery, so this validation IS the
    boundary."""
    with pytest.raises(UnsafeIdentifier):
        ident(bad, "column")


def test_a_bad_identifier_is_refused_wherever_it_reaches_a_template() -> None:
    with pytest.raises(UnsafeIdentifier):
        lookup_by_key(P, D, "Asset; DROP TABLE x", "Asset", ["Asset"])
    with pytest.raises(UnsafeIdentifier):
        lookup_by_key(P, D, T, "Asset", ["Asset`, (SELECT 1)"])
    with pytest.raises(UnsafeIdentifier):
        lookup_by_key(P, "Dimensions_Api; --", T, "Asset", ["Asset"])


def test_every_value_is_a_parameter_never_interpolated() -> None:
    """Not even a value that came from the catalogue. The keys are supplied at
    execution and the SQL carries only names."""
    query = lookup_by_keys(P, D, T, "Asset", ["Asset", "Asset_Description"])
    assert "@keys" in query.sql
    assert "keys" in query.parameters
    assert "'" not in query.sql


# --- what each template is for --------------------------------------------


def test_many_keys_resolve_in_one_query_not_one_per_row() -> None:
    """At a best-case ~300-400ms per interactive query, per-row resolution is
    not slow — it is unusable. A page of 200 rows is one query."""
    query = lookup_by_keys(P, D, T, "Asset", ["Asset"])
    assert "IN UNNEST(@keys)" in query.sql


def test_a_slowly_changing_dimension_reads_todays_row() -> None:
    """The convention the estate already honours by injecting
    `WHERE Effective_Date = CURRENT_DATE()`."""
    query = lookup_by_key(
        P, D, T, "Asset", ["Asset"], effective_date_column="Effective_Date"
    )
    assert "Effective_Date = CURRENT_DATE()" in query.sql


def test_typeahead_is_ordered_and_bounded() -> None:
    """Unordered results change between keystrokes, which reads as the picker
    flickering rather than as a missing ORDER BY."""
    query = search_labels(P, D, T, "Asset", "Asset_Description", limit=25)
    assert "ORDER BY Asset_Description" in query.sql
    assert "LIMIT 25" in query.sql


def test_a_fact_read_requires_its_grain() -> None:
    """There is no ungrained read. Without a grain there is no defensible answer
    to which rows a number belongs to."""
    with pytest.raises(ValueError, match="grain"):
        fact_measures_at_grain(P, "Facts_Api", "Asset_Transactions", [], ["Amount"])


def test_a_fact_read_projects_its_grain_alongside_its_measures() -> None:
    """So the caller can attribute each number to a row without a second query —
    and without Frame joining anything."""
    query = fact_measures_at_grain(
        P, "Facts_Api", "Asset_Transactions", ["Asset", "Period"], ["Amount", "Quantity"]
    )
    assert "SELECT Asset, Period, Amount, Quantity" in query.sql
    assert set(query.parameters) == {"Asset", "Period"}


def test_a_limit_is_always_present() -> None:
    """An unbounded scan is Frame's bill: Frame's own project submits and pays."""
    for query in [
        lookup_by_key(P, D, T, "Asset", ["Asset"]),
        lookup_by_keys(P, D, T, "Asset", ["Asset"]),
        search_labels(P, D, T, "Asset", "Asset_Description"),
        fact_measures_at_grain(P, "Facts_Api", "Asset_Transactions", ["Asset"], ["Amount"]),
    ]:
        assert "LIMIT" in query.sql
