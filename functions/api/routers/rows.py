"""Rows. One router, every Blueprint.

``{blueprintId}`` is a path parameter, not a module name. There is no
``risks.py`` and there never will be — the fitness suite fails the build if a
file appears here that is not on its allowlist, which is what keeps "zero
per-Blueprint code" demonstrable rather than aspirational.

Every handler is the same four steps: resolve the compiled Blueprint, resolve
the Principal, call the one library that decides, call the one function that
reads or writes. Nothing in this file decides anything.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query, Request

from api.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    RequestValidationError,
)
from api.dependencies.auth import CurrentUser
from api.schemas.rows import (
    AnnotationOut,
    PagePlanOut,
    QueryIn,
    RowOut,
    RowPageOut,
    RowWriteIn,
    RowWriteOut,
)
from lib.blueprint.compile import CompiledBlueprint
from lib.blueprint.store import BlueprintNotFound, load_compiled
from lib.grammar.ast import parse
from lib.permissions.evaluate import compile_rules, evaluate_row
from lib.permissions.model import Principal
from lib.permissions.trim import trim_row
from lib.principals import resolve_principal
from lib.rows.reader import (
    InvalidCursor,
    PageRequest,
    RowPage,
    SortSpec,
    read_page,
)
from lib.rows.source import FirestoreRowSource
from lib.rows.writer import WriteConflict, WriteContext, WriteRejected, write_row

router = APIRouter(tags=["rows"])


def _db(request: Request) -> Any:
    from lib.firestore import get_db

    return get_db()


Db = Annotated[Any, Depends(_db)]


def _compiled(db: Any, workspace_id: str, blueprint_id: str) -> CompiledBlueprint:
    try:
        return load_compiled(db, workspace_id, blueprint_id)
    except BlueprintNotFound as exc:
        raise NotFoundError(f"No Blueprint {blueprint_id!r} in workspace {workspace_id!r}") from exc


def _channel(request: Request) -> str:
    """How this write arrived. Recorded on every audit entry (PM-7).

    A client-declared header rather than an inference from the URL, because the
    same endpoint genuinely serves a grid edit, a paste and an import — and
    "changed by Maya" and "changed by an import Maya started" are different
    facts that a reviewer needs to tell apart.
    """
    declared = request.headers.get("x-frame-channel", "api").strip().lower()
    allowed = {"grid", "form", "api", "import", "undo", "automation", "bound_sheet"}
    return declared if declared in allowed else "api"


@router.post("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/query")
def query_rows(
    workspace_id: str,
    blueprint_id: str,
    user: CurrentUser,
    db: Db,
    request: Request,
    body: Annotated[QueryIn, Body()] = QueryIn(),
) -> RowPageOut:
    """A page of rows, trimmed for the caller.

    POST rather than GET because the filter is an AST. Encoding a tree into a
    query string means either a bespoke serialisation nobody else can read or a
    URL that exceeds what proxies will carry — and a filter truncated by a proxy
    returns the wrong rows silently.
    """
    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)

    try:
        page = read_page(
            compiled,
            compile_rules(compiled),
            principal,
            FirestoreRowSource(db, workspace_id, compiled),
            PageRequest(
                limit=body.limit,
                cursor=body.cursor,
                filter=parse(body.filter) if body.filter else None,
                sort=tuple(SortSpec(s.field_id, s.direction) for s in body.sort),
            ),
        )
    except InvalidCursor as exc:
        raise RequestValidationError(f"Invalid cursor: {exc}") from exc

    return _page_out(page, compiled)


@router.get("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows")
def list_rows(
    workspace_id: str,
    blueprint_id: str,
    user: CurrentUser,
    db: Db,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: str | None = None,
    sort: str | None = None,
) -> RowPageOut:
    """The unfiltered page, for clients that have no filter to send.

    Exists so the common case is a GET — cacheable, linkable, and visible in an
    access log — rather than everything being a POST because one case needs a
    body.
    """
    sorts: list[SortSpec] = []
    if sort:
        field_id = sort.lstrip("-")
        sorts.append(SortSpec(field_id, "desc" if sort.startswith("-") else "asc"))

    body = QueryIn(limit=limit, cursor=cursor)
    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)

    try:
        page = read_page(
            compiled,
            compile_rules(compiled),
            principal,
            FirestoreRowSource(db, workspace_id, compiled),
            PageRequest(limit=body.limit, cursor=body.cursor, sort=tuple(sorts)),
        )
    except InvalidCursor as exc:
        raise RequestValidationError(f"Invalid cursor: {exc}") from exc

    return _page_out(page, compiled)


@router.get("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/{row_id}")
def get_row(
    workspace_id: str,
    blueprint_id: str,
    row_id: str,
    user: CurrentUser,
    db: Db,
) -> RowOut:
    from lib.paths import row as row_path

    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)

    snapshot = row_path(db, workspace_id, blueprint_id, row_id).get()
    if not snapshot.exists:
        raise NotFoundError(f"No row {row_id!r}")

    stored = snapshot.to_dict() or {}
    stored.setdefault("id", row_id)
    decision = evaluate_row(compile_rules(compiled), principal, stored, compiled=compiled)

    trimmed = trim_row(stored, decision)
    if trimmed is None:
        # 404, not 403: a 403 confirms the row exists, which is a disclosure in
        # its own right on a register whose row set is itself sensitive. PM-6
        # existence masking generalises this; until it ships, the conservative
        # answer is the right one.
        raise NotFoundError(f"No row {row_id!r}")

    return _row_out(trimmed)


@router.post(
    "/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows",
    status_code=201,
)
def create_row(
    workspace_id: str,
    blueprint_id: str,
    user: CurrentUser,
    db: Db,
    request: Request,
    body: RowWriteIn,
) -> RowWriteOut:
    return _write(workspace_id, blueprint_id, None, user, db, request, body)


@router.patch("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/{row_id}")
def update_row(
    workspace_id: str,
    blueprint_id: str,
    row_id: str,
    user: CurrentUser,
    db: Db,
    request: Request,
    body: RowWriteIn,
) -> RowWriteOut:
    """PATCH, never PUT.

    PUT means "here is the whole row", and a whole-row save cannot express
    last-write-wins per cell (GR-8) — two people editing different cells of one
    row would lose an edit. The verb and the semantics have to agree or clients
    will reasonably assume the wrong one.
    """
    return _write(workspace_id, blueprint_id, row_id, user, db, request, body)


def _write(
    workspace_id: str,
    blueprint_id: str,
    row_id: str | None,
    user: CurrentUser,
    db: Any,
    request: Request,
    body: RowWriteIn,
) -> RowWriteOut:
    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)
    decision = _write_decision(compiled, principal, db, workspace_id, row_id)

    ctx = WriteContext(
        workspace_id=workspace_id,
        blueprint_id=blueprint_id,
        actor=principal.subject,
        channel=_channel(request),
        correlation_id=getattr(request.state, "correlation_id", None),
    )

    try:
        result = write_row(
            compiled, ctx,
            row_id=row_id,
            submitted_values=body.values,
            decision=decision,
            submitted_versions=body.field_versions,
            db=db,
        )
    except WriteConflict as exc:
        raise PreconditionFailedError(
            "A concurrent edit changed the same fields",
            extra={"fields": list(exc.fields), "current": exc.current},
        ) from exc
    except WriteRejected as exc:
        raise _rejection_to_http(exc) from exc

    return RowWriteOut(
        id=result.row_id,
        created=result.created,
        changed_fields=list(result.changed_fields),
        field_versions=result.field_versions,
        values=result.values,
    )


def _write_decision(
    compiled: CompiledBlueprint,
    principal: Principal,
    db: Any,
    workspace_id: str,
    row_id: str | None,
) -> Any:
    """The Decision the write is judged against.

    On update this is evaluated against the row as it currently stands, not
    against the submitted values. Evaluating against what the client sent would
    let a writer move a row into a scope they have rights over and edit it in
    the same request — the classic confused-deputy write.
    """
    from lib.paths import row as row_path

    rule_set = compile_rules(compiled)
    if row_id is None:
        return evaluate_row(rule_set, principal, {"values": {}}, compiled=compiled)

    snapshot = row_path(db, workspace_id, compiled.id, row_id).get()
    if not snapshot.exists:
        raise NotFoundError(f"No row {row_id!r}")
    stored = snapshot.to_dict() or {}
    stored.setdefault("id", row_id)
    return evaluate_row(rule_set, principal, stored, compiled=compiled)


def _rejection_to_http(exc: WriteRejected) -> Exception:
    """Map a refusal to a status a client can act on.

    Distinct codes because the correct client response differs: 403 means stop,
    422 means fix the values and resend, 409 means the row is not in a state
    that accepts this, and 413 means split the save.
    """
    match exc.code:
        case "forbidden" | "forbidden_fields":
            return AuthorizationError(
                exc.reason,
                extra={"fields": sorted(exc.outcome.rejected_fields)} if exc.outcome else {},
            )
        case "not_found":
            return NotFoundError(exc.reason)
        case "noop":
            return ConflictError(exc.reason)
        case "commit_too_large":
            from api.core.exceptions import PayloadTooLargeError

            return PayloadTooLargeError(exc.reason)
        case _:
            return RequestValidationError(
                exc.reason,
                extra={
                    "errors": [
                        {"fieldId": e.field_id, "message": e.message, "code": e.code}
                        for e in (exc.outcome.errors if exc.outcome else [])
                    ]
                },
            )


def _row_out(row: dict[str, Any]) -> RowOut:
    return RowOut(
        id=row.get("id", ""),
        values=row.get("values", {}),
        field_versions=row.get("fieldVersions", {}),
        lifecycle_status=row.get("lifecycleStatus", "draft"),
        updated_at=row.get("updatedAt"),
        updated_by=row.get("updatedBy"),
    )


def _page_out(page: RowPage, compiled: CompiledBlueprint) -> RowPageOut:
    return RowPageOut(
        rows=[_row_out(r) for r in page.rows],
        annotation=AnnotationOut(
            visible=page.annotation.visible,
            withheld=page.annotation.withheld,
            total=page.annotation.total,
            scope=page.annotation.scope,
            certainty=page.annotation.certainty,  # type: ignore[arg-type]
            ceiling=page.annotation.ceiling,
        ),
        cursor=page.cursor,
        has_more=page.has_more,
        column_stubs=sorted(page.column_stubs),
        plan=PagePlanOut(
            store_filters=page.plan.store_filters,
            post_filtered=page.plan.post_filtered,
            scanned=page.plan.scanned,
            rounds=page.plan.rounds,
            scan_budget_exhausted=page.plan.scan_budget_exhausted,
            reasons=page.plan.reasons,
            unsortable=page.plan.unsortable,
        ),
        blueprint_id=compiled.id,
        blueprint_version=compiled.version,
    )
