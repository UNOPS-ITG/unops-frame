"""Saved views.

The endpoint that makes Milestone 1's exit criterion demonstrable: two people
open the *same* saved view from the *same* URL and legitimately see different
rows and columns. That only works because a view carries a query and grants
nothing — the Decision is evaluated per reader on the row path, exactly as it is
without a view.

Reading a view therefore does not need a permission check of its own beyond
"may you read this Blueprint at all". The rows come back trimmed regardless.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from api.core.exceptions import AuthorizationError, NotFoundError, RequestValidationError
from api.dependencies.auth import CurrentUser
from api.schemas.base import RequestSchema, ResponseSchema
from api.schemas.rows import RowPageOut
from lib.blueprint.store import BlueprintNotFound, load_compiled
from lib.grammar.ast import parse
from lib.permissions.evaluate import compile_rules
from lib.principals import resolve_principal
from lib.rows.reader import InvalidCursor, PageRequest, SortSpec, read_page
from lib.rows.source import FirestoreRowSource
from lib.views.model import SavedView, ViewColumn, ViewScope, ViewSort
from lib.views.store import clear_default, delete_view, get_view, list_views, save_view
from lib.views.validate import validate_view

router = APIRouter(tags=["views"])


def _db(request: Request) -> Any:
    from lib.firestore import get_db

    return get_db()


Db = Annotated[Any, Depends(_db)]


def _compiled(db: Any, workspace_id: str, blueprint_id: str) -> Any:
    try:
        return load_compiled(db, workspace_id, blueprint_id)
    except BlueprintNotFound as exc:
        raise NotFoundError(f"No Blueprint {blueprint_id!r}") from exc


class ViewSortIn(RequestSchema):
    field_id: str
    direction: str = "asc"


class ViewColumnIn(RequestSchema):
    field_id: str
    width: int | None = None
    hidden: bool = False
    pinned: str | None = None


class ViewIn(RequestSchema):
    name: str
    scope: str = "personal"
    filter: dict[str, Any] | None = None
    sort: list[ViewSortIn] = []
    columns: list[ViewColumnIn] = []
    group_by: str | None = None
    row_height: str = "normal"


class ViewIssueOut(ResponseSchema):
    code: str
    message: str
    field_id: str | None = None


class ViewOut(ResponseSchema):
    id: str
    name: str
    scope: str
    author: str
    filter: dict[str, Any] | None = None
    sort: list[dict[str, Any]]
    columns: list[dict[str, Any]]
    group_by: str | None = None
    row_height: str
    blueprint_version: int
    is_mine: bool
    warnings: list[ViewIssueOut] = []
    """Non-fatal problems, carried on the view rather than only at save time.

    A view saved last quarter can become partly invalid when a Blueprint
    changes, and the person who opens it is rarely the person who saved it —
    telling them "this sort no longer works" beats an unexplained order.
    """


@router.get("/workspaces/{workspace_id}/blueprints/{blueprint_id}/views")
def list_saved_views(
    workspace_id: str, blueprint_id: str, user: CurrentUser, db: Db
) -> list[ViewOut]:
    compiled = _compiled(db, workspace_id, blueprint_id)
    views = list_views(db, workspace_id, blueprint_id, user.subject)
    return [_out(v, compiled, user.subject) for v in views]


@router.post(
    "/workspaces/{workspace_id}/blueprints/{blueprint_id}/views", status_code=201
)
def create_saved_view(
    workspace_id: str, blueprint_id: str, user: CurrentUser, db: Db, body: ViewIn
) -> ViewOut:
    compiled = _compiled(db, workspace_id, blueprint_id)
    view = _from_input(body, workspace_id, blueprint_id, user.subject, compiled.version, uuid.uuid4().hex)

    report = validate_view(view, compiled)
    if not report.ok:
        raise RequestValidationError(
            "This view cannot be saved",
            extra={"errors": [_issue(i) for i in report.errors]},
        )

    save_view(db, view)
    if view.scope is ViewScope.DEFAULT:
        clear_default(db, workspace_id, blueprint_id, view.id)
    return _out(view, compiled, user.subject)


@router.put("/workspaces/{workspace_id}/blueprints/{blueprint_id}/views/{view_id}")
def update_saved_view(
    workspace_id: str,
    blueprint_id: str,
    view_id: str,
    user: CurrentUser,
    db: Db,
    body: ViewIn,
) -> ViewOut:
    compiled = _compiled(db, workspace_id, blueprint_id)
    existing = get_view(db, workspace_id, blueprint_id, view_id)
    if existing is None:
        raise NotFoundError(f"No view {view_id!r}")
    _require_own(existing, user.subject)

    # The author does not change hands on edit. A shared view rewritten by
    # someone else would silently reassign responsibility for it, and PM-11
    # access review reads authorship.
    view = _from_input(body, workspace_id, blueprint_id, existing.author, compiled.version, view_id)

    report = validate_view(view, compiled)
    if not report.ok:
        raise RequestValidationError(
            "This view cannot be saved",
            extra={"errors": [_issue(i) for i in report.errors]},
        )

    save_view(db, view)
    if view.scope is ViewScope.DEFAULT:
        clear_default(db, workspace_id, blueprint_id, view.id)
    return _out(view, compiled, user.subject)


@router.delete(
    "/workspaces/{workspace_id}/blueprints/{blueprint_id}/views/{view_id}",
    status_code=204,
)
def delete_saved_view(
    workspace_id: str, blueprint_id: str, view_id: str, user: CurrentUser, db: Db
) -> None:
    existing = get_view(db, workspace_id, blueprint_id, view_id)
    if existing is None:
        raise NotFoundError(f"No view {view_id!r}")
    _require_own(existing, user.subject)
    delete_view(db, workspace_id, blueprint_id, view_id)


@router.get(
    "/workspaces/{workspace_id}/blueprints/{blueprint_id}/views/{view_id}/rows"
)
def read_view_rows(
    workspace_id: str,
    blueprint_id: str,
    view_id: str,
    user: CurrentUser,
    db: Db,
    limit: int = 100,
    cursor: str | None = None,
) -> RowPageOut:
    """The demonstration endpoint.

    Two principals calling this with the same view id get the same query and
    different results, because the query is the view's and the Decision is
    theirs. Nothing here consults the view about access.
    """
    from api.routers.rows import _page_out, resolve_corporate

    compiled = _compiled(db, workspace_id, blueprint_id)
    view = get_view(db, workspace_id, blueprint_id, view_id)
    if view is None:
        raise NotFoundError(f"No view {view_id!r}")
    if view.scope is ViewScope.PERSONAL and view.author != user.subject:
        raise NotFoundError(f"No view {view_id!r}")

    principal = resolve_principal(db, workspace_id, user)

    try:
        page = read_page(
            compiled,
            compile_rules(compiled),
            principal,
            FirestoreRowSource(db, workspace_id, compiled),
            PageRequest(
                limit=limit,
                cursor=cursor,
                filter=parse(view.filter) if view.filter else None,
                sort=tuple(SortSpec(s.field_id, s.direction) for s in view.sort),
            ),
        )
    except InvalidCursor as exc:
        raise RequestValidationError(f"Invalid cursor: {exc}") from exc

    resolve_corporate(page.rows, compiled, db, workspace_id, user.subject)
    return _page_out(page, compiled)


def _require_own(view: SavedView, subject: str) -> None:
    if view.author != subject:
        raise AuthorizationError(
            "Only the person who saved a view can change it",
            extra={"author": view.author},
        )


def _from_input(
    body: ViewIn,
    workspace_id: str,
    blueprint_id: str,
    author: str,
    blueprint_version: int,
    view_id: str,
) -> SavedView:
    return SavedView(
        id=view_id,
        name=body.name,
        blueprint_id=blueprint_id,
        workspace_id=workspace_id,
        scope=ViewScope(body.scope),
        author=author,
        filter=body.filter,
        sort=[ViewSort(field_id=s.field_id, direction=s.direction) for s in body.sort],  # type: ignore[arg-type]
        columns=[
            ViewColumn(
                field_id=c.field_id,
                width=c.width,
                hidden=c.hidden,
                pinned=c.pinned,  # type: ignore[arg-type]
            )
            for c in body.columns
        ],
        group_by=body.group_by,
        row_height=body.row_height,  # type: ignore[arg-type]
        blueprint_version=blueprint_version,
        updated_at=datetime.now(UTC),
    )


def _issue(issue: Any) -> dict[str, Any]:
    return {"code": issue.code, "message": issue.message, "fieldId": issue.field_id}


def _out(view: SavedView, compiled: Any, subject: str) -> ViewOut:
    report = validate_view(view, compiled)
    return ViewOut(
        id=view.id,
        name=view.name,
        scope=view.scope.value,
        author=view.author,
        filter=view.filter,
        # Camel-cased explicitly: these are nested plain models with no alias
        # generator, so `by_alias` alone leaves them snake_case and the response
        # ends up mixing conventions inside one envelope.
        sort=[{"fieldId": s.field_id, "direction": s.direction} for s in view.sort],
        columns=[
            {"fieldId": c.field_id, "width": c.width, "hidden": c.hidden, "pinned": c.pinned}
            for c in view.columns
        ],
        group_by=view.group_by,
        row_height=view.row_height,
        blueprint_version=view.blueprint_version,
        is_mine=view.author == subject,
        warnings=[ViewIssueOut(**_issue_fields(i)) for i in report.warnings],
    )


def _issue_fields(issue: Any) -> dict[str, Any]:
    return {"code": issue.code, "message": issue.message, "field_id": issue.field_id}
