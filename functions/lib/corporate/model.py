"""The corporate-data catalogue: what Frame can bind a field to.

**Discovered, not authored.** An admin registers a *Source* — which BigQuery
project, which datasets to exclude — and everything else is derived by a
scheduled sweep of the warehouse's own metadata. There is no registration queue
and no steward turnaround target, because the data team has already built the
catalogue: `Metadata_Api` declares business keys, column roles, policy tags,
domains, stewards and the relationship graph.

That removes the feature's biggest governance risk and replaces it with a
smaller one, named here rather than discovered later: an always-current
catalogue changes without a human in the loop, so a dataset dropped or
re-pointed upstream silently retires a dimension that thousands of Frame rows
reference. Detection is instant and free; remediation is a scheduled migration
with a real downstream cascade, and the two must never be conflated.

**Frame never aggregates.** A Fact names a column on a relation that is
*already at the declared grain*. Frame composes no GROUP BY, no JOIN, no window
function and no aggregation on any path. If a number does not exist at a grain,
that is a request to the data platform team for a mart — they own the definition
of "expenditure to date" and Frame does not.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Disclosure(StrEnum):
    OPEN = "open"
    """Key, code, label and attributes are disclosable to any authenticated
    staff member. Mirrored into a narrow projection and served at Frame speed,
    with no consent screen and no warehouse query on any read path.

    Assigned by mechanical probe and never by assertion — see `classify.py`."""

    ENTITLED = "entitled"
    """Rows, columns or labels vary by principal, **or the audience question
    could not be answered mechanically**. Resolved live, per viewer, in the
    user's own context, where BigQuery's IAM and policy tags are the enforcement
    point and Frame implements none of it.

    The default, and the safe direction: the governing line is that Frame caches
    no label anyone may be denied."""


class ColumnRole(StrEnum):
    DIMENSION = "dimension"
    MEASURE = "measure"
    UNKNOWN = "unknown"
    """Declared for ~99% of columns upstream. The rest are surfaced for
    correction rather than guessed at — a heuristic that is right most of the
    time produces a fact binding that is wrong some of the time, silently."""


class Attribute(_Strict):
    """One column on a dimension, as Frame may carry it onto a row."""

    name: str
    label: str
    description: str | None = None
    data_type: str
    role: ColumnRole = ColumnRole.UNKNOWN
    policy_tag: str | None = None
    is_business_key: bool = False

    @property
    def is_open(self) -> bool:
        """Level 0 is the declared unrestricted tag; absent means untagged.

        An untagged column is treated as open only in combination with the other
        checks in `classify.py` — a missing tag is an absence of evidence, not
        evidence of absence, and the four checks exist because no single one of
        them is sufficient.
        """
        tag = (self.policy_tag or "").strip()
        return tag == "" or tag.startswith("Level 0")


class Measure(_Strict):
    """A numeric column on a fact, at the fact's declared grain.

    Never an aggregate. Frame reads the value that is already there.
    """

    name: str
    label: str
    description: str | None = None
    data_type: str
    policy_tag: str | None = None


class Relation(_Strict):
    """An edge in the warehouse's own relationship graph.

    Read from `Datahub_Table_Reference` rather than inferred. Both `ai-bob` and
    Prism independently rebuilt weaker versions of this graph — one by stripping
    `_id` suffixes and matching names, emitting `confidence: "high"` with no
    ground truth; the other by declaring foreign-key fields that are never
    populated. BigQuery's own foreign keys are irrelevant: none are declared,
    and none can be on a view.
    """

    from_dataset: str
    from_table: str
    from_column: str
    to_dataset: str
    to_table: str
    to_column: str
    kind: str
    """MANY_TO_ONE (fact to dimension) or ONE_TO_MANY (dimension to dimension)."""

    verb: str | None = None
    join_sql: str | None = None
    inner: bool = False
    enabled: bool = True


class RelationStatus(StrEnum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    """Swept away or re-pointed upstream. Stops serving new picks immediately;
    stored labels keep rendering with a staleness marker, and the change raises
    on an integrity panel. Frame does not auto-rewrite governed rows from the
    warehouse — detection is instant, remediation is a costed migration, and
    conflating them is how a permission or a total silently changes."""


class Dimension(_Strict):
    """Master data: a thing Frame fields can look up."""

    id: str
    """`dataset.table`, stable across sweeps. Frame rows store this, so it can
    never be derived from a label."""

    dataset: str
    table: str
    label: str
    description: str | None = None
    business_domain: str | None = None
    data_steward: str | None = None

    business_key: str | None = None
    """The column a stored reference keys on. Without one the relation cannot be
    bound at all: a lookup with no stable key stores a label, and a label is not
    an identity."""

    effective_date_column: str | None = None
    """Slowly-changing dimensions. A convention the estate already honours by
    injecting `WHERE Effective_Date = CURRENT_DATE()`."""

    attributes: list[Attribute] = Field(default_factory=list)
    disclosure: Disclosure = Disclosure.ENTITLED
    label_visibility: Disclosure = Disclosure.ENTITLED
    """Whether the stored label snapshot may be shown to anyone.

    Separate from `disclosure` because most master-data labels are not sensitive
    and some are. Where this is `entitled`, an unresolvable key renders as a
    PM-5 restricted stub rather than a snapshot — without the distinction, the
    snapshot is a quiet bypass of the warehouse policy.
    """

    status: RelationStatus = RelationStatus.ACTIVE
    classification_reasons: list[str] = Field(default_factory=list)
    """Why it landed where it did. Recorded because "why can I not pick from
    this?" is otherwise unanswerable without re-running the probe."""

    @property
    def bindable(self) -> bool:
        return self.status is RelationStatus.ACTIVE and self.business_key is not None


class Fact(_Strict):
    """Transactional data: a number Frame can show beside a row.

    At the declared grain, always. Frame composes no aggregation.
    """

    id: str
    dataset: str
    table: str
    label: str
    description: str | None = None
    business_domain: str | None = None
    data_steward: str | None = None

    grain: list[str] = Field(default_factory=list)
    """The dimension ids this fact is keyed by, from the relationship graph.
    This is what makes a corporate figure bindable to a Frame row: without a
    declared grain there is no defensible way to say which rows a number
    belongs to."""

    measures: list[Measure] = Field(default_factory=list)

    restricted_columns: list[str] = Field(default_factory=list)
    """Every column on the fact carrying a tag above Level 0 — not only its
    measures.

    A fact's projected columns include its grain keys and its descriptive
    attributes, and those are exactly where the sensitive ones live: a
    recruitment fact's tagged columns are panel member names, not the count.
    Classifying on measures alone read such a table as open, because the one
    numeric column on it was harmless.
    """

    disclosure: Disclosure = Disclosure.ENTITLED
    status: RelationStatus = RelationStatus.ACTIVE
    classification_reasons: list[str] = Field(default_factory=list)

    @property
    def bindable(self) -> bool:
        return self.status is RelationStatus.ACTIVE and bool(self.grain) and bool(self.measures)


class Source(_Strict):
    """What an admin actually registers. Everything else is discovered.

    Deliberately tiny: a BigQuery project, the datasets to exclude, and the
    guard rails. Anything more would be a registration queue by another name.
    """

    id: str
    project: str
    excluded_datasets: list[str] = Field(default_factory=list)
    """Frame lists the datasets and selects all by default. Exclusion rather
    than inclusion, so a dataset added upstream is swept in rather than silently
    missing."""

    metadata_dataset: str = "Metadata_Api"
    """Where the data team's catalogue lives. Frame points at the published
    `_Api` interface layer, not the base tables — `ai-bob` points at the base
    datasets while every platform integration YAML points at `_Api`, an existing
    inconsistency Frame resolves deliberately rather than inherits."""

    max_bytes_billed: int = 2_000_000_000
    """Per query. Frame's own project submits and pays, so an unbounded scan is
    Frame's bill. Enforced rather than advisory: BigQuery refuses the job."""

    require_partition_filter: bool = True
    enabled: bool = True
