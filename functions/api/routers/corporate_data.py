"""Corporate data: the catalogue, and what may be bound to it (PRD 14).

Three surfaces, and the split between them matters.

**The catalogue** is Frame-owned metadata about the warehouse. Reading it
discloses table and column *names*, not data — but names are not nothing, so it
is authenticated and scoped to the workspace. It is not user-context: it is
Frame's own swept record.

**A lookup** reads actual warehouse data, so it runs in the user's own context
and BigQuery is the enforcement point. Frame implements none of it.

**A source** is admin configuration. Registering one is a governance action —
it decides which project Frame will submit billed queries against.

The endpoint that does NOT exist is as important: there is no "run this SQL".
Frame emits four fixed templates and nothing else, and an endpoint that accepted
a query would make that fence unenforceable in one line.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from api.core.exceptions import AuthorizationError, NotFoundError, RequestValidationError
from api.dependencies.auth import CurrentUser
from api.schemas.base import RequestSchema, ResponseSchema
from lib.corporate.classify import Probe, classify_relation
from lib.corporate.model import Dimension, Fact, Source
from lib.corporate.sweep import Catalogue, sweep

router = APIRouter(tags=["corporate-data"])

SOURCES = "corporateSources"
CATALOGUE = "corporateCatalogue"


def _db(request: Request) -> Any:
    from lib.firestore import get_db

    return get_db()


Db = Annotated[Any, Depends(_db)]


# --- wire shapes ----------------------------------------------------------


class SourceIn(RequestSchema):
    """What an admin registers. Deliberately tiny — everything else is swept."""

    id: str
    project: str
    excluded_datasets: list[str] = []
    metadata_dataset: str = "Metadata_Api"
    max_bytes_billed: int = 2_000_000_000
    enabled: bool = True


class SourceOut(ResponseSchema):
    id: str
    project: str
    excluded_datasets: list[str]
    metadata_dataset: str
    max_bytes_billed: int
    enabled: bool
    last_swept_at: Any | None = None
    dimensions: int = 0
    facts: int = 0


class AttributeOut(ResponseSchema):
    name: str
    label: str
    data_type: str
    role: str
    is_business_key: bool
    restricted: bool
    """Carries a policy tag above Level 0. Surfaced so a Blueprint author picking
    attributes to carry onto a row can see which ones will make the whole
    binding entitled."""


class DimensionOut(ResponseSchema):
    id: str
    label: str
    description: str | None = None
    business_domain: str | None = None
    data_steward: str | None = None
    business_key: str | None = None
    disclosure: str
    bindable: bool
    reasons: list[str] = []
    """Why it landed where it did. "Why can I not pick from this?" is otherwise
    unanswerable without re-running the probe."""

    attributes: list[AttributeOut] = []


class MeasureOut(ResponseSchema):
    name: str
    label: str
    data_type: str
    restricted: bool


class FactOut(ResponseSchema):
    id: str
    label: str
    description: str | None = None
    business_domain: str | None = None
    data_steward: str | None = None
    grain: list[str]
    """The dimension ids this fact is keyed by. A Frame row can bind to it only
    where the row already references every dimension in the grain — otherwise
    there is no defensible answer to which rows the number belongs to."""

    disclosure: str
    bindable: bool
    reasons: list[str] = []
    measures: list[MeasureOut] = []


# --- sources --------------------------------------------------------------


@router.get("/workspaces/{workspace_id}/corporate/sources")
def list_sources(workspace_id: str, user: CurrentUser, db: Db) -> list[SourceOut]:
    from lib.paths import workspace

    out: list[SourceOut] = []
    for snapshot in workspace(db, workspace_id).collection(SOURCES).stream():
        data = snapshot.to_dict() or {}
        data.setdefault("id", snapshot.id)
        source = Source.model_validate({k: v for k, v in data.items() if k in Source.model_fields})
        out.append(
            SourceOut(
                id=source.id,
                project=source.project,
                excluded_datasets=source.excluded_datasets,
                metadata_dataset=source.metadata_dataset,
                max_bytes_billed=source.max_bytes_billed,
                enabled=source.enabled,
                last_swept_at=data.get("lastSweptAt"),
                dimensions=int(data.get("dimensionCount") or 0),
                facts=int(data.get("factCount") or 0),
            )
        )
    return out


@router.put("/workspaces/{workspace_id}/corporate/sources/{source_id}", status_code=200)
def register_source(
    workspace_id: str, source_id: str, user: CurrentUser, db: Db, body: SourceIn
) -> SourceOut:
    """Register or update a source.

    A governance action: it decides which project Frame submits billed queries
    against. Restricted to workspace managers rather than anyone who can edit a
    Blueprint, and audited — not because registering is dangerous in itself, but
    because the project named here is the one that receives the invoice.
    """
    from lib.paths import workspace
    from lib.principals import resolve_principal

    principal = resolve_principal(db, workspace_id, user)
    if "manager" not in principal.workspace_roles and "admin" not in principal.workspace_roles:
        raise AuthorizationError(
            "Registering a corporate-data source is a workspace-manager action: it "
            "decides which project Frame submits billed queries against."
        )

    if body.id != source_id:
        raise RequestValidationError("the source id in the body must match the URL")
    if body.max_bytes_billed <= 0:
        raise RequestValidationError(
            "max_bytes_billed must be positive — an unbounded scan is Frame's bill"
        )

    source = Source(
        id=body.id,
        project=body.project,
        excluded_datasets=body.excluded_datasets,
        metadata_dataset=body.metadata_dataset,
        max_bytes_billed=body.max_bytes_billed,
        enabled=body.enabled,
    )
    workspace(db, workspace_id).collection(SOURCES).document(source_id).set(
        source.model_dump(mode="json")
    )

    return SourceOut(
        id=source.id,
        project=source.project,
        excluded_datasets=source.excluded_datasets,
        metadata_dataset=source.metadata_dataset,
        max_bytes_billed=source.max_bytes_billed,
        enabled=source.enabled,
    )


# --- the catalogue --------------------------------------------------------


@router.get("/workspaces/{workspace_id}/corporate/dimensions")
def list_dimensions(
    workspace_id: str,
    user: CurrentUser,
    db: Db,
    # Aliased, because FastAPI does not apply the wire alias generator to query
    # parameters — so without this the envelope is camelCase and the query
    # string is snake_case, and a client that assumes one convention silently
    # gets the default instead of an error.
    bindable_only: Annotated[bool, Query(alias="bindableOnly")] = True,
) -> list[DimensionOut]:
    """What a Blueprint author can point a lookup field at.

    Defaults to bindable only, because a list containing things that cannot be
    picked is a list where every author eventually tries one.
    """
    catalogue = _load_catalogue(db, workspace_id)
    dimensions = catalogue.bindable_dimensions if bindable_only else list(catalogue.dimensions.values())
    return [_dimension_out(d) for d in sorted(dimensions, key=lambda d: d.label.lower())]


@router.get("/workspaces/{workspace_id}/corporate/facts")
def list_facts(
    workspace_id: str,
    user: CurrentUser,
    db: Db,
    bindable_only: Annotated[bool, Query(alias="bindableOnly")] = True,
) -> list[FactOut]:
    catalogue = _load_catalogue(db, workspace_id)
    facts = catalogue.bindable_facts if bindable_only else list(catalogue.facts.values())
    return [_fact_out(f) for f in sorted(facts, key=lambda f: f.label.lower())]


@router.get("/workspaces/{workspace_id}/corporate/dimensions/{dimension_id}")
def get_dimension(
    workspace_id: str, dimension_id: str, user: CurrentUser, db: Db
) -> DimensionOut:
    catalogue = _load_catalogue(db, workspace_id)
    dimension = catalogue.dimensions.get(dimension_id)
    if dimension is None:
        raise NotFoundError(f"No dimension {dimension_id!r} in the catalogue")
    return _dimension_out(dimension)


def _load_catalogue(db: Any, workspace_id: str) -> Catalogue:
    """The swept catalogue, as stored.

    Read from Frame's own record rather than swept on demand: a sweep is a
    scheduled job against the warehouse, and running one per page load would
    make browsing the catalogue the most expensive thing in the product.
    """
    from lib.paths import workspace

    document = workspace(db, workspace_id).collection(CATALOGUE).document("current").get()
    if not document.exists:
        return Catalogue()

    data = document.to_dict() or {}
    return sweep(
        Source.model_validate(data.get("source", {"id": "unknown", "project": "unknown"})),
        data.get("dictionary", []),
        data.get("tables", []),
        data.get("relations", []),
    )


# The probe results are stored per relation by the sweep job; until it has run,
# nothing is open. That default is the safe one and it is deliberate: an
# unclassified relation is not a public one.
UNPROBED = Probe()


def _dimension_out(dimension: Dimension) -> DimensionOut:
    disclosure, reasons = classify_relation(dimension, UNPROBED)
    return DimensionOut(
        id=dimension.id,
        label=dimension.label,
        description=dimension.description,
        business_domain=dimension.business_domain,
        data_steward=dimension.data_steward,
        business_key=dimension.business_key,
        disclosure=disclosure.value,
        bindable=dimension.bindable,
        reasons=reasons,
        attributes=[
            AttributeOut(
                name=a.name,
                label=a.label,
                data_type=a.data_type,
                role=a.role.value,
                is_business_key=a.is_business_key,
                restricted=not a.is_open,
            )
            for a in dimension.attributes
        ],
    )


def _fact_out(fact: Fact) -> FactOut:
    disclosure, reasons = classify_relation(fact, UNPROBED)
    restricted = set(fact.restricted_columns)
    return FactOut(
        id=fact.id,
        label=fact.label,
        description=fact.description,
        business_domain=fact.business_domain,
        data_steward=fact.data_steward,
        grain=fact.grain,
        disclosure=disclosure.value,
        bindable=fact.bindable,
        reasons=reasons,
        measures=[
            MeasureOut(
                name=m.name,
                label=m.label,
                data_type=m.data_type,
                restricted=m.name in restricted,
            )
            for m in fact.measures
        ],
    )
