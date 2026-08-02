"""The three metadata queries the sweep runs.

Separate from `sql.py` because these read the data team's *catalogue*, not their
data. They are exempt from the four-template fence for a reason that is worth
stating rather than assuming: the fence exists so Frame never computes a
corporate figure. Reading `Datahub_Data_Dictionary` computes nothing about the
organisation — it reads a list of column names.

They are not exempt from anything else. Same bytes ceiling, same labels, same
timeout, same parameterisation.

Filtered to the published `_Api` interface layer, not the base datasets. That is
a deliberate resolution of an existing estate inconsistency: `ai-bob` points at
the base datasets while every platform integration YAML points at `_Api`, and
`_Api` is where the descriptions and metadata coverage actually live.
"""

from __future__ import annotations

from lib.corporate.sql import Query, ident, project_id

DICTIONARY_COLUMNS = (
    "Dataset_Name", "Table_Name", "Table_Description", "Column_Position",
    "Column_Name", "Column_Name_Description", "Data_Type", "Column_Type",
    "Business_Key_Flag", "Business_Key", "Effective_Date_Flag",
    "Effective_Date_Column", "Policy_Tag", "Business_Domain",
    "Data_Steward_Name", "Table_Enabled_Flag", "Table_Column_Enabled_Flag",
)

TABLE_COLUMNS = (
    "Dataset_Name", "Table_Name", "Table_Description", "Business_Key",
    "Partition_Column", "Cluster_Column", "Table_Status", "Enabled_Flag",
    "Table_Deleted_Flag", "Secure_Column_Flag", "Effective_Date_Flag",
    "Business_Domain",
)

RELATION_COLUMNS = (
    "Dataset_Name", "Table_Name", "Column_Name", "Reference_Dataset_Name",
    "Reference_Table_Name", "Reference_Column_Name", "Relationship_Type",
    "Relationship_Path", "Relationship_Verb", "SQL_Join_Text",
    "Inner_Join_Flag", "Enabled_Flag", "Data_Type_Match_Flag",
)

# The datasets a sweep considers. Suffix-matched rather than hardcoded in full,
# so a second published layer (`Integrations_Api`) can be added by extending
# this tuple rather than by editing three queries.
LAYERS = ("Dimensions_Api", "Facts_Api")


def _in_layers() -> str:
    return "(" + ", ".join(f"'{ident(layer, 'dataset')}'" for layer in LAYERS) + ")"


def dictionary_query(project: str, metadata_dataset: str) -> Query:
    """Table and column metadata: the whole catalogue in one query."""
    columns = ", ".join(ident(c, "column") for c in DICTIONARY_COLUMNS)
    return Query(
        # noqa justification as in sql.py: every interpolated token passed
        # `ident`, and there are no caller-supplied values here at all.
        sql=(
            f"SELECT {columns} "  # noqa: S608 - identifiers pass `ident`/`project_id`; no caller values
            f"FROM `{project_id(project)}.{ident(metadata_dataset, 'dataset')}"
            f".Datahub_Data_Dictionary` "
            f"WHERE Dataset_Name IN {_in_layers()} "
            "ORDER BY Dataset_Name, Table_Name, Column_Position"
        ),
    )


def tables_query(project: str, metadata_dataset: str) -> Query:
    """Keys, partitioning, and the retirement signals."""
    columns = ", ".join(ident(c, "column") for c in TABLE_COLUMNS)
    return Query(
        sql=(
            f"SELECT {columns} "  # noqa: S608 - identifiers pass `ident`/`project_id`; no caller values
            f"FROM `{project_id(project)}.{ident(metadata_dataset, 'dataset')}"
            f".Datahub_Table` "
            f"WHERE Dataset_Name IN {_in_layers()} "
            "ORDER BY Dataset_Name, Table_Name"
        ),
    )


def relations_query(project: str, metadata_dataset: str) -> Query:
    """The relationship graph — 3,629 declared edges at the last count.

    Not filtered to `Dimensions_Api`. Every consumer found in the estate does
    filter that way, which is why the 2,780 fact-to-dimension edges are
    maintained and unused, and why two teams built weaker inference beside a
    graph that already existed.
    """
    columns = ", ".join(ident(c, "column") for c in RELATION_COLUMNS)
    return Query(
        sql=(
            f"SELECT {columns} "  # noqa: S608 - identifiers pass `ident`/`project_id`; no caller values
            f"FROM `{project_id(project)}.{ident(metadata_dataset, 'dataset')}"
            f".Datahub_Table_Reference` "
            "WHERE Enabled_Flag = 'YES' "
            "ORDER BY Relationship_Type, Table_Name"
        ),
    )
