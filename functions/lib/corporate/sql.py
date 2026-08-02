"""The only SQL Frame emits against the warehouse.

**Frame never aggregates.** Four templates, and no fifth. Frame composes no
GROUP BY, no JOIN, no window function and no aggregation function on any path.
A registry Fact names a column on a relation that is *already at the declared
grain*; if a number does not exist at a grain, that is a request to the data
platform team for a mart, not a feature request for Frame — they own the
definition of "expenditure to date" and Frame does not.

That fence is mechanised rather than promised: `assert_no_aggregation` runs over
every statement this module produces, and `test_corporate_sql.py` runs it over
all four templates. A fifth template added without the check is caught by the
same test asserting the template count.

**Every value is a query parameter.** Never interpolated, not even an identifier
that "came from our own catalogue" — the catalogue is swept from a system Frame
does not control, and a table name is exactly the kind of value that is trusted
right up until someone can influence it. Identifiers cannot be parameterised in
BigQuery, so they are validated against a strict pattern instead and the
validation is the security boundary.

**Every query is bounded.** `maximum_bytes_billed` is set on every job, because
Frame's own project submits and pays: an unbounded scan is Frame's bill. It is
enforced by BigQuery rather than checked by Frame — the job is refused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
"""BigQuery's own identifier rule, applied to anything that reaches a query
unparameterised. Anchored, length-bounded, and no dots — a dotted value would
let a swept table name escape its dataset."""

BANNED = re.compile(
    r"\b(GROUP\s+BY|JOIN|OVER\s*\(|UNION|SUM|AVG|COUNT|MIN|MAX|ARRAY_AGG|STRING_AGG"
    r"|APPROX_|PERCENTILE|RANK|ROW_NUMBER|LAG|LEAD)\b",
    re.IGNORECASE,
)


class UnsafeIdentifier(ValueError):
    """A dataset, table or column name that cannot be safely interpolated."""


class AggregationAttempted(RuntimeError):
    """The fence, tripped. See the module docstring."""


def ident(value: str, what: str) -> str:
    if not IDENTIFIER.match(value or ""):
        raise UnsafeIdentifier(
            f"{what} {value!r} is not a plain BigQuery identifier. Frame will not "
            "interpolate it — the catalogue is swept from a system Frame does not "
            "control, and a name is exactly the value that is trusted until someone "
            "can influence it."
        )
    return value


def assert_no_aggregation(sql: str) -> None:
    """Frame never aggregates, asserted rather than trusted."""
    match = BANNED.search(sql)
    if match:
        raise AggregationAttempted(
            f"this statement contains {match.group(0)!r}. Frame composes no GROUP BY, "
            "JOIN, window function or aggregation on any path. If a number does not "
            "exist at a grain, that is a mart request to the data platform team — "
            "they own the definition and Frame does not."
        )


SCALAR_TYPES = {
    "STRING", "BYTES", "INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC",
    "BIGNUMERIC", "BOOL", "BOOLEAN", "DATE", "DATETIME", "TIME", "TIMESTAMP",
}


def scalar_type(declared: str | None) -> str:
    """A catalogue data type, normalised to what BigQuery's parameter API wants.

    Carried on the query rather than left to the caller because a mismatch is a
    *runtime* failure — `IN UNNEST(@keys)` against an INT64 column with a
    STRING array is rejected by BigQuery with a signature error, and the caller
    has no way to know the column's type that Frame does not already have from
    the sweep. Guessing STRING works for most dimensions and fails on every
    numeric key, which is the worst distribution for finding it in testing.
    """
    name = (declared or "STRING").strip().upper()
    return name if name in SCALAR_TYPES else "STRING"


@dataclass(frozen=True, slots=True)
class Query:
    sql: str
    parameters: dict[str, str] = dc_field(default_factory=dict)
    """Named parameter -> its BigQuery type, e.g. ``{"keys": "ARRAY<INT64>"}``.

    Types, not values: the values arrive at execution. The only things
    interpolated into `sql` are identifiers that passed `ident`.
    """

    def __post_init__(self) -> None:
        assert_no_aggregation(self.sql)


PROJECT_ID = re.compile(r"^[a-z][a-z0-9\-]{4,28}[a-z0-9]$")
"""Google's own project-id rule. Looser than `IDENTIFIER` because a project id
may contain hyphens, and stricter in every other respect — it is still the value
that names which organisation's data a query reads."""


def project_id(value: str) -> str:
    if not PROJECT_ID.match(value or ""):
        raise UnsafeIdentifier(
            f"project {value!r} is not a plain GCP project id. This value names "
            "which organisation's data a query reads; it is not interpolated "
            "unvalidated."
        )
    return value


def _table(project: str, dataset: str, table: str) -> str:
    return f"`{project_id(project)}.{ident(dataset, 'dataset')}.{ident(table, 'table')}`"


# --- the four templates ---------------------------------------------------


def lookup_by_key(
    project: str, dataset: str, table: str, key_column: str, columns: list[str],
    *, key_type: str = "STRING", effective_date_column: str | None = None, limit: int = 1,
) -> Query:
    """TEMPLATE 1 — resolve one key to its row.

    What a stored reference needs when its label snapshot is unusable: the key is
    known, the row is wanted. One row, by definition, so no ordering is needed
    and none is emitted.
    """
    projected = ", ".join(ident(c, "column") for c in columns) or "*"
    where = [f"{ident(key_column, 'key column')} = @key"]
    if effective_date_column:
        # The slowly-changing-dimension convention the estate already honours.
        where.append(f"{ident(effective_date_column, 'effective date column')} = CURRENT_DATE()")

    return Query(
        # S608: every interpolated token passed `ident`; every value is a
        # named parameter. See the module docstring.
        sql=(
            f"SELECT {projected} FROM {_table(project, dataset, table)} "  # noqa: S608 - identifiers pass `ident`, values are parameters
            f"WHERE {' AND '.join(where)} LIMIT {int(limit)}"
        ),
        parameters={"key": scalar_type(key_type)},
    )


def lookup_by_keys(
    project: str, dataset: str, table: str, key_column: str, columns: list[str],
    *, key_type: str = "STRING", effective_date_column: str | None = None, limit: int = 500,
) -> Query:
    """TEMPLATE 2 — resolve MANY keys in one query.

    The batching rule, in template form. Never a query per row: a grid page of
    two hundred rows referencing a dimension is one query, not two hundred. At a
    best-case ~300–400ms per interactive query, per-row resolution is not slow,
    it is unusable.
    """
    projected = ", ".join(ident(c, "column") for c in columns) or "*"
    where = [f"{ident(key_column, 'key column')} IN UNNEST(@keys)"]
    if effective_date_column:
        where.append(f"{ident(effective_date_column, 'effective date column')} = CURRENT_DATE()")

    return Query(
        # S608: every interpolated token passed `ident`; every value is a
        # named parameter. See the module docstring.
        sql=(
            f"SELECT {projected} FROM {_table(project, dataset, table)} "  # noqa: S608 - identifiers pass `ident`, values are parameters
            f"WHERE {' AND '.join(where)} LIMIT {int(limit)}"
        ),
        parameters={"keys": f"ARRAY<{scalar_type(key_type)}>"},
    )


def search_labels(
    project: str, dataset: str, table: str, key_column: str, label_column: str,
    *, effective_date_column: str | None = None, limit: int = 50,
) -> Query:
    """TEMPLATE 3 — the picker's typeahead.

    Served from a cached slice for an `open` dimension and never per keystroke.
    This template exists for the `entitled` case, where the slice cannot be
    cached and the query runs in the user's own context — debounced, bounded,
    and ordered so the answer is stable between keystrokes.
    """
    key = ident(key_column, "key column")
    label = ident(label_column, "label column")
    where = [f"STARTS_WITH(LOWER({label}), LOWER(@prefix))"]
    if effective_date_column:
        where.append(f"{ident(effective_date_column, 'effective date column')} = CURRENT_DATE()")

    return Query(
        sql=(
            f"SELECT {key}, {label} FROM {_table(project, dataset, table)} "  # noqa: S608 - identifiers pass `ident`, values are parameters
            f"WHERE {' AND '.join(where)} ORDER BY {label} LIMIT {int(limit)}"
        ),
        parameters={"prefix": "STRING"},
    )


def fact_measures_at_grain(
    project: str, dataset: str, table: str, grain_columns: list[str],
    measure_columns: list[str], *, grain_types: dict[str, str] | None = None,
    limit: int = 500,
) -> Query:
    """TEMPLATE 4 — read facts at their declared grain.

    Reads. Does not compute. Every row returned is already at the grain the data
    team declared, and the measure columns are read as stored. The whole point of
    refusing to aggregate is that the number Frame shows is the number the
    warehouse holds, so a disagreement between a Frame view and a Prism dashboard
    is a data question rather than a "which tool is right" question.
    """
    if not grain_columns:
        raise ValueError("a fact read needs its grain columns; there is no ungrained read")

    grain = [ident(c, "grain column") for c in grain_columns]
    measures = [ident(c, "measure column") for c in measure_columns]
    projected = ", ".join(grain + measures)
    where = " AND ".join(f"{c} IN UNNEST(@{c})" for c in grain)

    return Query(
        sql=(
            f"SELECT {projected} FROM {_table(project, dataset, table)} "  # noqa: S608 - identifiers pass `ident`, values are parameters
            f"WHERE {where} LIMIT {int(limit)}"
        ),
        parameters={
            c: f"ARRAY<{scalar_type((grain_types or {}).get(c))}>" for c in grain
        },
    )


TEMPLATES = (lookup_by_key, lookup_by_keys, search_labels, fact_measures_at_grain)
"""Every statement Frame emits. A fifth is a design decision, not a patch — the
test asserting this count is what makes that true rather than aspirational."""
