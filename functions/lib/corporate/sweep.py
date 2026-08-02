"""The discovery sweep: warehouse metadata in, bindable catalogue out.

Pure. It takes rows already fetched and returns a catalogue, so the whole of the
derivation is testable against captured fixtures with no BigQuery, no
credentials and no cost. The three queries that feed it live in `bigquery.py`.

What it reads, and why each matters:

* **`Datahub_Data_Dictionary`** — the whole catalogue in one query: table and
  column descriptions, business domain, data steward, policy tag, and
  DIMENSION/MEASURE per column. `Column_Type` is what makes a fact binding
  possible at all.
* **`Datahub_Table`** — business key, partition and cluster columns, and the
  retirement signals (`Table_Status`, `Enabled_Flag`, `Table_Deleted_Flag`).
* **`Datahub_Table_Reference`** — the relationship graph, with 2,780 measured
  fact-to-dimension edges. Fact *grain* is declared upstream, at scale, which is
  the thing that makes a corporate figure bindable to a Frame row.

Nothing here is inferred from a naming convention. That is the difference
between this and the two weaker graphs the estate already contains.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from lib.corporate.model import (
    Attribute,
    ColumnRole,
    Dimension,
    Fact,
    Measure,
    Relation,
    RelationStatus,
    Source,
)

DIMENSION_DATASET_SUFFIX = "Dimensions_Api"
FACT_DATASET_SUFFIX = "Facts_Api"


@dataclass(slots=True)
class Catalogue:
    dimensions: dict[str, Dimension] = dc_field(default_factory=dict)
    facts: dict[str, Fact] = dc_field(default_factory=dict)
    relations: list[Relation] = dc_field(default_factory=list)
    skipped: list[tuple[str, str]] = dc_field(default_factory=list)
    """(id, reason). Surfaced rather than dropped: "why can I not bind to this?"
    is a question an admin will ask about a table they can see in BigQuery, and
    silence makes it unanswerable."""

    @property
    def bindable_dimensions(self) -> list[Dimension]:
        return [d for d in self.dimensions.values() if d.bindable]

    @property
    def bindable_facts(self) -> list[Fact]:
        return [f for f in self.facts.values() if f.bindable]


def _yes(value: Any) -> bool:
    return str(value or "").strip().upper() in {"YES", "Y", "TRUE", "1"}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _role(value: Any) -> ColumnRole:
    match str(value or "").strip().upper():
        case "DIMENSION":
            return ColumnRole.DIMENSION
        case "MEASURE":
            return ColumnRole.MEASURE
        case _:
            return ColumnRole.UNKNOWN


def _relation_id(dataset: str, table: str) -> str:
    return f"{dataset}.{table}"


def sweep(
    source: Source,
    dictionary: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> Catalogue:
    """Derive the catalogue. Pure, and deliberately so."""
    catalogue = Catalogue()

    table_meta = {
        _relation_id(row["Dataset_Name"], row["Table_Name"]): row for row in tables
    }

    columns: dict[str, list[dict[str, Any]]] = {}
    for row in dictionary:
        columns.setdefault(_relation_id(row["Dataset_Name"], row["Table_Name"]), []).append(row)

    for relation_id, cols in columns.items():
        dataset, table = relation_id.split(".", 1)
        if dataset in source.excluded_datasets:
            catalogue.skipped.append((relation_id, "dataset excluded on the Source"))
            continue

        meta = table_meta.get(relation_id, {})
        head = cols[0]

        status = _status(meta, head)
        if status is None:
            catalogue.skipped.append((relation_id, "retired or deleted upstream"))
            continue

        if dataset.endswith(DIMENSION_DATASET_SUFFIX):
            catalogue.dimensions[relation_id] = _dimension(relation_id, dataset, table, cols, meta, status)
        elif dataset.endswith(FACT_DATASET_SUFFIX):
            catalogue.facts[relation_id] = _fact(relation_id, dataset, table, cols, meta, status)
        else:
            # Dataset membership is what declares dimension versus fact. A table
            # in neither is not a third kind — it is outside the published
            # interface layer, and binding to it would tie Frame to something
            # nobody committed to keeping stable.
            catalogue.skipped.append(
                (relation_id, "not in the published Dimensions_Api or Facts_Api layer")
            )

    catalogue.relations = _relations(relations)
    _apply_grain(catalogue)
    return catalogue


def _status(meta: dict[str, Any], head: dict[str, Any]) -> RelationStatus | None:
    """Retirement signals are declared upstream rather than inferred.

    ``None`` means "do not surface at all": a table the data team has deleted or
    disabled is not a quarantine case, it is gone. Quarantine is for a relation
    Frame rows still reference, and that decision belongs to reconciliation
    against stored values rather than to the sweep.
    """
    if _yes(meta.get("Table_Deleted_Flag")):
        return None
    if meta and not _yes(meta.get("Enabled_Flag")):
        return None
    if not _yes(head.get("Table_Enabled_Flag", "YES")):
        return None
    return RelationStatus.ACTIVE


def _dimension(
    relation_id: str,
    dataset: str,
    table: str,
    cols: list[dict[str, Any]],
    meta: dict[str, Any],
    status: RelationStatus,
) -> Dimension:
    head = cols[0]
    attributes = [
        Attribute(
            name=c["Column_Name"],
            label=_text(c.get("Column_Name_Description")) or c["Column_Name"],
            description=_text(c.get("Column_Name_Description")),
            data_type=str(c.get("Data_Type") or "STRING"),
            role=_role(c.get("Column_Type")),
            policy_tag=_text(c.get("Policy_Tag")),
            is_business_key=_yes(c.get("Business_Key_Flag")),
        )
        for c in cols
        if _yes(c.get("Table_Column_Enabled_Flag", "YES"))
    ]

    business_key = _text(meta.get("Business_Key")) or _text(head.get("Business_Key"))
    if business_key is None:
        # Fall back to the flagged column. A dimension with no key at all stays
        # unbindable rather than being bound on a guess — a lookup with no
        # stable key stores a label, and a label is not an identity.
        business_key = next((a.name for a in attributes if a.is_business_key), None)

    effective = None
    if _yes(head.get("Effective_Date_Flag")):
        effective = _text(head.get("Effective_Date_Column"))

    return Dimension(
        id=relation_id,
        dataset=dataset,
        table=table,
        label=_text(meta.get("Table_Description")) or _text(head.get("Table_Description")) or table,
        description=_text(meta.get("Table_Description")) or _text(head.get("Table_Description")),
        business_domain=_text(head.get("Business_Domain")),
        data_steward=_text(head.get("Data_Steward_Name")),
        business_key=business_key,
        effective_date_column=effective,
        attributes=attributes,
        status=status,
    )


def _fact(
    relation_id: str,
    dataset: str,
    table: str,
    cols: list[dict[str, Any]],
    meta: dict[str, Any],
    status: RelationStatus,
) -> Fact:
    head = cols[0]
    measures = [
        Measure(
            name=c["Column_Name"],
            label=_text(c.get("Column_Name_Description")) or c["Column_Name"],
            description=_text(c.get("Column_Name_Description")),
            data_type=str(c.get("Data_Type") or "NUMERIC"),
            policy_tag=_text(c.get("Policy_Tag")),
        )
        for c in cols
        # Declared, not inferred from type. A numeric column is not a measure —
        # a year, a code and a count are all integers, and summing a year is the
        # kind of wrong that survives review.
        if _role(c.get("Column_Type")) is ColumnRole.MEASURE
        and _yes(c.get("Table_Column_Enabled_Flag", "YES"))
    ]

    # EVERY tagged column, not only the tagged measures. A fact's sensitive
    # columns are usually its grain keys and descriptive attributes — a
    # recruitment fact's tagged columns are panel member names, not the count —
    # so classifying on measures alone reads such a table as open.
    restricted = [
        c["Column_Name"]
        for c in cols
        if not _is_open_tag(c.get("Policy_Tag"))
        and _yes(c.get("Table_Column_Enabled_Flag", "YES"))
    ]

    return Fact(
        id=relation_id,
        dataset=dataset,
        table=table,
        label=_text(meta.get("Table_Description")) or _text(head.get("Table_Description")) or table,
        description=_text(meta.get("Table_Description")) or _text(head.get("Table_Description")),
        business_domain=_text(head.get("Business_Domain")),
        data_steward=_text(head.get("Data_Steward_Name")),
        measures=measures,
        restricted_columns=restricted,
        status=status,
    )


def _is_open_tag(value: Any) -> bool:
    tag = str(value or "").strip()
    return tag == "" or tag.startswith("Level 0")


def _relations(rows: list[dict[str, Any]]) -> list[Relation]:
    out: list[Relation] = []
    for row in rows:
        if not _yes(row.get("Enabled_Flag", "YES")):
            # A disabled edge is kept out of the graph rather than kept and
            # filtered later: every consumer that forgot the filter would join
            # on a relationship the data team has withdrawn.
            continue
        out.append(
            Relation(
                from_dataset=row["Dataset_Name"],
                from_table=row["Table_Name"],
                from_column=row["Column_Name"],
                to_dataset=row["Reference_Dataset_Name"],
                to_table=row["Reference_Table_Name"],
                to_column=row["Reference_Column_Name"],
                kind=str(row.get("Relationship_Type") or "MANY_TO_ONE"),
                verb=_text(row.get("Relationship_Verb")),
                join_sql=_text(row.get("SQL_Join_Text")),
                inner=_yes(row.get("Inner_Join_Flag")),
                enabled=True,
            )
        )
    return out


def _apply_grain(catalogue: Catalogue) -> None:
    """A fact's grain is the set of dimensions it is keyed by.

    Taken from the declared graph, never from column names. This is the step
    that makes a corporate figure bindable to a Frame row: without a grain there
    is no defensible answer to "which rows does this number belong to", and the
    honest response to that is to refuse the binding rather than to guess.
    """
    for relation in catalogue.relations:
        fact_id = _relation_id(relation.from_dataset, relation.from_table)
        dimension_id = _relation_id(relation.to_dataset, relation.to_table)
        fact = catalogue.facts.get(fact_id)
        if fact is None or dimension_id not in catalogue.dimensions:
            continue
        if dimension_id not in fact.grain:
            fact.grain.append(dimension_id)

    for fact in catalogue.facts.values():
        fact.grain.sort()
