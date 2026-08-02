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
from lib.corporate.model import Dimension, Fact, Source
from lib.corporate.sweep import Catalogue

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


class ConnectionOut(ResponseSchema):
    connected: bool
    email: str | None = None
    granted_at: str | None = None
    scopes: list[str] = []


# --- the connector --------------------------------------------------------


@router.get("/corporate/connection")
def get_connection(user: CurrentUser, db: Db) -> ConnectionOut:
    """Whether this person has connected their BigQuery access.

    Not workspace-scoped: a person's consent is theirs, granted once, and used
    in every workspace they work in. Scoping it per workspace would mean
    consenting again for each one, which is both worse for them and a stronger
    claim than Frame needs to make.
    """
    store = _tokens(db)
    grant = store.get(user.subject)
    return ConnectionOut(
        connected=store.is_connected(user.subject),
        email=grant.email if grant else None,
        granted_at=grant.granted_at if grant else None,
        scopes=list(grant.scopes) if grant else [],
    )


@router.get("/corporate/connection/start")
def start_connection(request: Request, user: CurrentUser, db: Db) -> Any:
    """Begin consent. Redirects to Google."""
    from fastapi.responses import RedirectResponse

    from lib.corporate.consent import (
        STATE_COOKIE,
        STATE_MAX_AGE_SECONDS,
        build_consent_url,
        new_state,
    )
    from lib.corporate.tokens import BIGQUERY_SCOPE

    settings = request.app.state.settings
    if not settings.oauth_client_id or not settings.oauth_client_secret:
        raise RequestValidationError(
            "The BigQuery connector is not configured on this deployment: no OAuth "
            "client. Corporate data cannot be connected until it is."
        )

    store = _tokens(db)
    if store.is_connected(user.subject):
        # Already granted. Sending them through consent again would produce a
        # screen that offers nothing and, with prompt=consent, a pointless
        # re-grant.
        raise RequestValidationError("BigQuery is already connected for this account")

    state = new_state(user.subject)
    consent = build_consent_url(
        client_id=settings.oauth_client_id,
        redirect_uri=_redirect_uri(request, settings),
        required_scopes=[BIGQUERY_SCOPE],
        granted_scopes=store.granted_scopes(user.subject),
        state=state,
    )

    response = RedirectResponse(url=consent.url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        consent.state_cookie_value,
        httponly=True,
        secure=settings.environment != "local",
        # Lax rather than Strict: the cookie has to survive Google's top-level
        # redirect back. Strict would drop it and every consent would fail with
        # "no flow in progress".
        samesite="lax",
        max_age=STATE_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.get("/corporate/connection/callback")
def finish_connection(
    request: Request, user: CurrentUser, db: Db, code: str = "", state: str = ""
) -> Any:
    """Google's callback. Authenticated, because it returns through IAP.

    That is what lets the state be checked against the *authenticated* subject
    rather than against a session resolved afterwards — closing a replay where
    one person's consent lands on another's account.
    """
    from lib.corporate.consent import STATE_COOKIE, ConsentRejected, verify_state

    settings = request.app.state.settings

    try:
        verify_state(
            returned_state=state,
            cookie_state=request.cookies.get(STATE_COOKIE),
            authenticated_subject=user.subject,
        )
    except ConsentRejected as exc:
        return _popup_close(str(exc), ok=False)

    if not code:
        return _popup_close("Google did not return an authorisation code.", ok=False)

    import httpx

    exchange = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.oauth_client_id,
            "client_secret": settings.oauth_client_secret,
            "code": code,
            "redirect_uri": _redirect_uri(request, settings),
            "grant_type": "authorization_code",
        },
        timeout=15.0,
    )
    if exchange.status_code != 200:
        return _popup_close("Google refused the authorisation code.", ok=False)

    payload = exchange.json()
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        # Google omits it on a repeat grant it considers already given. Without
        # one the connector works for an hour and then stops, which is the
        # hardest kind of failure to attribute.
        return _popup_close(
            "Google did not issue a refresh token. Remove Frame from your Google "
            "account permissions and connect again.",
            ok=False,
        )

    store = _tokens(db)
    granted = list(payload.get("scope", "").split()) or list(store.granted_scopes(user.subject))
    store.store(user.subject, refresh_token, granted, email=user.email)

    return _popup_close("BigQuery connected.")


@router.delete("/corporate/connection", status_code=200)
def disconnect(user: CurrentUser, db: Db) -> ConnectionOut:
    """Revoke at Google, then forget locally.

    Both, and in that order. Deleting the local record alone leaves a live grant
    the user believes is gone and Frame can no longer see.
    """
    _tokens(db).disconnect(user.subject)
    return ConnectionOut(connected=False)


def _redirect_uri(request: Request, settings: Any) -> str:
    configured = getattr(settings, "corporate_oauth_redirect_uri", "")
    if configured:
        return str(configured)
    # Same origin the request arrived on, so a local run and a deployment do not
    # need different configuration to work.
    return str(request.url_for("finish_connection"))


def _tokens(db: Any) -> Any:
    from api.core.config import get_settings
    from lib.corporate.crypto import build_cipher
    from lib.corporate.tokens import TokenStore

    settings = get_settings()
    cipher = build_cipher(
        environment=str(settings.environment),
        kms_key_name=getattr(settings, "corporate_kms_key", None),
        impersonate=getattr(settings, "corporate_kms_service_account", None),
    )
    return TokenStore(
        db,
        cipher,
        client_id=getattr(settings, "oauth_client_id", "") or "",
        client_secret=getattr(settings, "oauth_client_secret", "") or "",
    )


def _popup_close(message: str, *, ok: bool = True) -> Any:
    """A page that reports and closes itself.

    The consent flow runs in a popup so the user does not lose the register they
    were editing. Escaped, because the message can carry text from an error path
    and a connector page is a poor place to learn about injection.
    """
    from html import escape

    from fastapi.responses import HTMLResponse

    from lib.corporate.consent import STATE_COOKIE

    colour = "#0F9D58" if ok else "#d93025"
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Frame</title>"
        "<style>body{font:16px/1.5 system-ui,sans-serif;display:grid;place-items:center;"
        "height:100vh;margin:0;background:#f7f8fa}div{max-width:34rem;padding:2rem;"
        "border-radius:12px;background:#fff;box-shadow:0 2px 12px rgba(0,0,0,.08);"
        f"text-align:center}}p{{margin:0;color:{colour}}}</style></head>"
        f"<body><div><p>{escape(message)}</p></div>"
        "<script>setTimeout(function(){window.close()},2500)</script></body></html>"
    )
    response = HTMLResponse(content=body)
    response.delete_cookie(STATE_COOKIE, path="/")
    return response


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

    Stored one document per relation, because the real warehouse — ~960
    relations, ~15,700 columns — is roughly 12 MB and does not fit in a
    Firestore document.
    """
    from lib.corporate.sweep_job import load_catalogue

    return load_catalogue(db, workspace_id)


def _dimension_out(dimension: Dimension) -> DimensionOut:
    """Rendered from the stored classification.

    Not re-classified here. The sweep ran the probe with credentials this
    request does not have, and re-running the classifier against an empty probe
    would report every relation as entitled with a reason about a probe that in
    fact succeeded — turning a stored fact into a misleading one.
    """
    return DimensionOut(
        id=dimension.id,
        label=dimension.label,
        description=dimension.description,
        business_domain=dimension.business_domain,
        data_steward=dimension.data_steward,
        business_key=dimension.business_key,
        disclosure=dimension.disclosure.value,
        bindable=dimension.bindable,
        reasons=dimension.classification_reasons,
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
    restricted = set(fact.restricted_columns)
    return FactOut(
        id=fact.id,
        label=fact.label,
        description=fact.description,
        business_domain=fact.business_domain,
        data_steward=fact.data_steward,
        grain=fact.grain,
        disclosure=fact.disclosure.value,
        bindable=fact.bindable,
        reasons=fact.classification_reasons,
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
