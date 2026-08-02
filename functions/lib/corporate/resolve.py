"""Turning stored corporate references into what a reader may see.

The rule this module exists to keep: **one query per dimension per page, never
one per row.** A page of two hundred rows referencing two dimensions is two
queries. At BigQuery's best-case ~300-400ms per interactive query — most of it
orchestration rather than execution, and unfixable warehouse-side because
results are not cached for tables under row-level security — per-row resolution
is not slow, it is unusable.

Three outcomes, and the difference between the last two is the whole point:

* an **open** dimension renders its stored snapshot, marked stale past 90 days.
  No query at all: that is what the snapshot is for, and it is what lets the
  grid filter, sort, group, export and search without touching the warehouse.
* an **entitled** dimension renders the label resolved live in *this reader's*
  own context, or a PM-5 restricted stub if it could not be. Never the cached
  one — a cached label on an entitled dimension is a quiet bypass of the
  warehouse policy, and quiet is the worst kind.
* a **quarantined or missing** relation renders the stored key, marked, because
  hiding it would make the row look empty rather than orphaned, and those call
  for different actions.

Resolution failure is never fatal. A warehouse that is down, a user who has not
connected, a dimension whose base table moved: each produces stubs on one
column, not a 500 on the register. The reader can still work; the column says
it does not know.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from lib.corporate.model import Dimension, Disclosure
from lib.corporate.reference import from_value, render

logger = logging.getLogger(__name__)

MAX_KEYS_PER_QUERY = 500
"""One page's worth of distinct keys, which is also `lookup_by_keys`' own limit.

A page cannot reference more distinct keys than it has rows, so this binds in
practice only for a page larger than any the reader serves — it is a guard
against a caller that batches several pages together, not a routine truncation.
"""


@dataclass(slots=True)
class ResolutionPlan:
    """Which keys are wanted from which dimension, before anything is fetched."""

    by_dimension: dict[str, set[str]] = dc_field(default_factory=dict)
    fields_by_dimension: dict[str, set[str]] = dc_field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not self.by_dimension


def plan_resolution(rows: list[dict[str, Any]], compiled: Any) -> ResolutionPlan:
    """Collect every corporate key on the page, grouped by dimension.

    Pure, and separate from fetching, so the batching rule is checkable without
    a warehouse: a test asserts one entry per dimension no matter how many rows
    reference it.
    """
    plan = ResolutionPlan()

    for field_id, cf in compiled.fields.items():
        if cf.storage != "corporate_ref":
            continue
        dimension_id = cf.definition.dimension
        if not dimension_id:
            # Declared as corporate data with no dimension chosen. Nothing to
            # resolve; the renderer reports it rather than guessing.
            continue

        keys = plan.by_dimension.setdefault(dimension_id, set())
        plan.fields_by_dimension.setdefault(dimension_id, set()).add(field_id)

        for row in rows:
            ref = from_value(row.get("values", {}).get(field_id))
            if ref is not None:
                keys.add(ref.key)

    # A dimension every row left empty is not worth a query.
    plan.by_dimension = {d: k for d, k in plan.by_dimension.items() if k}
    return plan


def apply_resolution(
    rows: list[dict[str, Any]],
    plan: ResolutionPlan,
    dimensions: dict[str, Dimension | None],
    resolved: dict[str, dict[str, str]],
    *,
    now: Any = None,
) -> None:
    """Rewrite the stored values in place, through `render`.

    In place because the caller has already trimmed the page and building a
    second copy of every row to change one field is the kind of allocation that
    only shows up at fifty thousand rows.
    """
    for dimension_id, field_ids in plan.fields_by_dimension.items():
        dimension = dimensions.get(dimension_id)
        labels = resolved.get(dimension_id, {})

        for row in rows:
            values = row.get("values")
            if not isinstance(values, dict):
                continue
            for field_id in field_ids:
                stored = values.get(field_id)
                # A restricted stub stays a restricted stub. Field-level
                # permission has already spoken and this module does not
                # revisit it — that would be a second evaluator.
                if isinstance(stored, dict) and stored.get("restricted") is True:
                    continue
                ref = from_value(stored)
                if ref is None:
                    continue
                values[field_id] = render(
                    ref, dimension, resolved_label=labels.get(ref.key), now=now
                )


def load_dimensions(db: Any, workspace_id: str, ids: set[str]) -> dict[str, Dimension | None]:
    """The referenced dimensions, and only those.

    Not the whole catalogue: the real one is ~960 relations and ~12 MB, and a
    register that loaded all of it to render one column would make every page
    read the most expensive thing in the product.

    A missing id maps to `None` rather than being absent, so `render` gets the
    orphaned case explicitly instead of the caller having to distinguish "not
    fetched" from "not there".
    """
    from lib.corporate.sweep_job import CATALOGUE_COLLECTION, CURRENT, RELATIONS
    from lib.paths import workspace

    relations = (
        workspace(db, workspace_id)
        .collection(CATALOGUE_COLLECTION)
        .document(CURRENT)
        .collection(RELATIONS)
    )

    out: dict[str, Dimension | None] = {}
    for dimension_id in ids:
        snapshot = relations.document(dimension_id.replace(".", "__")).get()
        if not snapshot.exists:
            out[dimension_id] = None
            continue
        data = snapshot.to_dict() or {}
        data.pop("kind", None)
        try:
            out[dimension_id] = Dimension.model_validate(data)
        except Exception:  # noqa: BLE001 - a malformed catalogue row is orphaned, not fatal
            logger.warning("Catalogue entry %s could not be read as a dimension", dimension_id)
            out[dimension_id] = None
    return out


def resolve_labels(
    plan: ResolutionPlan,
    dimensions: dict[str, Dimension | None],
    source: Any,
    credential: Any,
    *,
    billing_project: str,
    workspace_id: str,
    client: Any = None,
) -> dict[str, dict[str, str]]:
    """Live labels for the entitled dimensions on this page, in the user's context.

    One query per dimension. Open dimensions are skipped entirely — their stored
    snapshot is what renders, and querying for a label Frame is already allowed
    to cache would be paying latency and money to reach a known conclusion.

    Every failure is swallowed to an empty result for that dimension. The column
    then renders as restricted stubs, which is the correct reading of "this
    reader could not be shown a label" whether the cause was a missing consent,
    a denied table or a warehouse outage.
    """
    from lib.corporate.executor import JobConfig
    from lib.corporate.sql import lookup_by_keys

    out: dict[str, dict[str, str]] = {}
    if credential is None or source is None:
        return out

    for dimension_id, keys in plan.by_dimension.items():
        dimension = dimensions.get(dimension_id)
        if dimension is None or not dimension.bindable:
            continue
        if dimension.label_visibility is not Disclosure.ENTITLED:
            continue

        label_column = _label_column(dimension)
        key_column = dimension.business_key
        if label_column is None or not key_column:
            continue

        try:
            query = lookup_by_keys(
                source.project,
                dimension.dataset,
                dimension.table,
                key_column,
                [key_column, label_column],
                key_type=_key_type(dimension),
                effective_date_column=dimension.effective_date_column,
                limit=MAX_KEYS_PER_QUERY,
            )
            runner = client or _default_client()
            result = runner.run(
                query,
                {"keys": sorted(keys)[:MAX_KEYS_PER_QUERY]},
                JobConfig(
                    project=billing_project,
                    location=source.location,
                    max_bytes_billed=source.max_bytes_billed,
                    workspace_id=workspace_id,
                    surface="row-resolve",
                ),
                credential,
            )
        except Exception as exc:  # noqa: BLE001 - a register must survive a warehouse outage
            logger.warning("Resolving %s failed: %s", dimension_id, exc)
            continue

        out[dimension_id] = {
            str(row.get(key_column)): str(row.get(label_column) or row.get(key_column))
            for row in result.rows
            if row.get(key_column) is not None
        }

    return out


def _default_client() -> Any:
    from lib.corporate.bigquery import BigQueryClient

    return BigQueryClient()


def _label_column(dimension: Dimension) -> str | None:
    """The column a person would recognise a row by.

    Restricted attributes are never used: a column carrying a policy tag above
    Level 0 is one BigQuery may withhold, and projecting it can fail the whole
    query rather than one field.
    """
    candidates = [
        a
        for a in dimension.attributes
        if a.is_open and not a.is_business_key and a.data_type.upper() in {"STRING", "TEXT"}
    ]
    if not candidates:
        return None
    for wanted in ("name", "label", "title", "description"):
        for attribute in candidates:
            if wanted in attribute.name.lower():
                return attribute.name
    return candidates[0].name


def _key_type(dimension: Dimension) -> str:
    """The declared type of the business key.

    Carried because `IN UNNEST(@keys)` against an INT64 column with a STRING
    array is a runtime signature error, and guessing STRING works for most
    dimensions and fails on every numeric key — the worst distribution for
    finding it in testing.
    """
    for attribute in dimension.attributes:
        if attribute.name == dimension.business_key:
            return attribute.data_type
    return "STRING"
