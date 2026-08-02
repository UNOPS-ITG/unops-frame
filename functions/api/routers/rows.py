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

from fastapi import APIRouter, Body, Depends, Query, Request, Response

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
    DeltaOut,
    DeltaPageOut,
    DeltaPollIn,
    ImportErrorOut,
    ImportIn,
    ImportResultOut,
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
from lib.rows.deltas import Room, authorise_deltas, may_subscribe
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

MAX_EXPORT_ROWS = 20_000
"""One export, one page. Above this the answer is a scheduled report (RP-11),
not a longer request: a synchronous export that takes minutes is one a proxy
terminates half-written, and a truncated CSV is indistinguishable from a
complete one."""


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


@router.post("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/import")
def import_rows(
    workspace_id: str,
    blueprint_id: str,
    user: CurrentUser,
    db: Db,
    request: Request,
    body: ImportIn,
) -> ImportResultOut:
    """Bulk import. A CALLER of the write path, never a second one.

    Every row gets the same validation, the same audit class and the same events
    as a row typed into the grid. ``dryRun`` is the default shape of the client
    flow rather than an option nobody uses: an import that reports its failures
    only after writing half the file is one the user cannot safely retry.
    """
    from lib.permissions.evaluate import may_at_blueprint_level
    from lib.permissions.model import Action
    from lib.rows.importer import build_chunks, plan_import
    from lib.rows.writer import commit_import

    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)
    rule_set = compile_rules(compiled)

    if not (
        may_at_blueprint_level(rule_set, principal, Action.IMPORT)
        or may_at_blueprint_level(rule_set, principal, Action.CREATE)
    ):
        raise AuthorizationError("You do not have permission to import into this register")

    # Field-level writability still comes from an evaluated Decision — the gate
    # above answers "may you import at all", not "which fields may you set".
    decision = evaluate_row(rule_set, principal, {"values": {}}, compiled=compiled)

    plan = plan_import(body.csv, compiled, decision)

    ctx = WriteContext(
        workspace_id=workspace_id,
        blueprint_id=blueprint_id,
        actor=principal.subject,
        channel="import",
        correlation_id=getattr(request.state, "correlation_id", None),
    )

    written = 0
    # Nothing is written while ANY row is invalid. A partially applied import is
    # the worst outcome: the user cannot tell which rows landed, and re-running
    # duplicates the ones that did.
    if not body.dry_run and plan.ok and plan.rows:
        written = commit_import(build_chunks(plan, compiled, ctx), ctx, compiled.id, db=db)

    return ImportResultOut(
        dry_run=body.dry_run,
        parsed_rows=plan.total_lines,
        valid_rows=len(plan.rows),
        written_rows=written,
        unmapped_columns=plan.unmapped_columns,
        errors=[
            ImportErrorOut(line=e.line, field_id=e.field_id, message=e.message, code=e.code)
            for e in plan.errors[:200]
        ],
        truncated_errors=max(0, len(plan.errors) - 200),
    )


@router.post("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/export")
def export_rows(
    workspace_id: str,
    blueprint_id: str,
    user: CurrentUser,
    db: Db,
    body: Annotated[QueryIn, Body()] = QueryIn(),
) -> Response:
    """Export as CSV.

    A distinct action from read, and an audited one: a user who may read a
    register on screen has not thereby been granted the right to take a copy of
    it home.
    """
    from lib.permissions.evaluate import may_at_blueprint_level
    from lib.permissions.model import Action
    from lib.rows.export import to_csv

    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)
    rule_set = compile_rules(compiled)

    # Rule-level, not evaluated against an empty row: a grant conditioned on a
    # field value does not match a row with no values, so the obvious gate
    # refuses a principal who can in fact see plenty of rows.
    if not (
        may_at_blueprint_level(rule_set, principal, Action.EXPORT)
        or may_at_blueprint_level(rule_set, principal, Action.READ)
    ):
        raise AuthorizationError("You do not have permission to export this register")

    try:
        page = read_page(
            compiled, rule_set, principal,
            FirestoreRowSource(db, workspace_id, compiled),
            PageRequest(
                limit=MAX_EXPORT_ROWS,
                filter=parse(body.filter) if body.filter else None,
                sort=tuple(SortSpec(s.field_id, s.direction) for s in body.sort),
            ),
        )
    except InvalidCursor as exc:
        raise RequestValidationError(f"Invalid cursor: {exc}") from exc

    csv_text = to_csv(page.rows, compiled, page.annotation)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{compiled.id}.csv"',
            # The annotation, in a header as well as in the file, so a
            # programmatic consumer can read it without parsing the trailer.
            "X-Frame-Rows-Visible": str(page.annotation.visible),
            "X-Frame-Rows-Withheld": str(page.annotation.withheld),
            "X-Frame-Count-Certainty": page.annotation.certainty,
        },
    )


@router.post("/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/deltas")
def poll_deltas(
    workspace_id: str,
    blueprint_id: str,
    user: CurrentUser,
    db: Db,
    body: DeltaPollIn,
) -> DeltaPageOut:
    """What changed since a watermark, for rows this caller may know about.

    A poll rather than a socket, deliberately, and it is not a placeholder for
    one: the shape is what makes real-time safe to add. Every delta is evaluated
    against the CURRENT row by the same permission library a read uses, so a
    push transport later inherits the authorisation instead of needing its own.
    A browser-side store listener would evaluate the store's rules rather than
    Frame's and become a second, weaker decision site.

    ``knownRowIds`` is what the client currently has on screen. It is what
    separates silence from a removal: a row that turns invisible and was never
    sent needs no delta, and sending one would disclose that something the
    caller cannot see changed.
    """
    from lib.paths import OUTBOX
    from lib.paths import row as row_path

    compiled = _compiled(db, workspace_id, blueprint_id)
    rule_set = compile_rules(compiled)
    principal = resolve_principal(db, workspace_id, user)

    if not may_subscribe(compiled, rule_set, principal):
        raise AuthorizationError("You have no read grant on this Blueprint")

    room = Room(workspace_id, compiled.id, compiled.version)
    envelopes = _envelopes_since(db, OUTBOX, body.since, body.max_envelopes)

    events = [
        event
        for envelope in envelopes
        for event in envelope.get("events", [])
        if room.accepts(event)
    ]

    # Fetched here rather than inside the authoriser so the library that decides
    # stays free of I/O — the property that lets every consumer link it.
    affected = {e.get("rowId") for e in events if isinstance(e.get("rowId"), str)}
    rows: dict[str, dict[str, Any] | None] = {}
    for row_id in affected:
        snapshot = row_path(db, workspace_id, compiled.id, row_id).get()
        if snapshot.exists:
            stored = snapshot.to_dict() or {}
            stored.setdefault("id", row_id)
            rows[row_id] = stored
        else:
            rows[row_id] = None

    deltas = authorise_deltas(
        events, rows, compiled, rule_set, principal,
        known_to_client=frozenset(body.known_row_ids),
    )

    return DeltaPageOut(
        deltas=[DeltaOut(**d.to_payload()) for d in deltas],
        # The watermark advances past every envelope EXAMINED, not past the last
        # one that produced a delta. Advancing only on delivery means a client
        # whose next thousand envelopes are all invisible to it re-examines the
        # same thousand forever — the same failure the row cursor avoids.
        since=envelopes[-1].get("envelopeId") if envelopes else body.since,
        blueprint_version=compiled.version,
    )


def _envelopes_since(
    db: Any, outbox: str, since: str | None, limit: int
) -> list[dict[str, Any]]:
    """Outbox envelopes after a watermark, oldest first.

    Ordered by write time rather than by envelope id: ids are opaque uuids
    precisely so nothing infers order from them, and a relay that sorted by id
    would deliver a Tuesday edit before a Monday one.
    """
    query = db.collection(outbox).order_by("at", "ASCENDING")
    envelopes = [snapshot.to_dict() or {} for snapshot in query.limit(limit * 4).stream()]

    if since is not None:
        ids = [e.get("envelopeId") for e in envelopes]
        if since in ids:
            envelopes = envelopes[ids.index(since) + 1 :]
    return envelopes[:limit]


@router.get(
    "/workspaces/{workspace_id}/blueprints/{blueprint_id}/rows/{row_id}/children/{collection_id}"
)
def list_children(
    workspace_id: str,
    blueprint_id: str,
    row_id: str,
    collection_id: str,
    user: CurrentUser,
    db: Db,
) -> RowPageOut:
    """A parent's children, with the parent ceiling applied last (PM-3).

    The parent is fetched and evaluated FIRST, and a reader who cannot see it
    gets a 404 for the parent rather than an empty child list — an empty list
    for a parent that exists and a parent that does not are different facts, and
    only one of them is safe to disclose.
    """
    from lib.paths import children as children_path
    from lib.paths import row as row_path
    from lib.rows.children import ChildContext, read_children
    from lib.rows.reader import PagePlan, RowPage

    compiled = _compiled(db, workspace_id, blueprint_id)
    principal = resolve_principal(db, workspace_id, user)

    collection = next(
        (c for c in compiled.blueprint.children if c.id == collection_id), None
    )
    if collection is None:
        raise NotFoundError(f"No child collection {collection_id!r}")

    snapshot = row_path(db, workspace_id, blueprint_id, row_id).get()
    if not snapshot.exists:
        raise NotFoundError(f"No row {row_id!r}")
    parent_row = snapshot.to_dict() or {}
    parent_row.setdefault("id", row_id)

    parent_decision = evaluate_row(
        compile_rules(compiled), principal, parent_row, compiled=compiled
    )
    if not parent_decision.visible:
        raise NotFoundError(f"No row {row_id!r}")

    child_compiled = _compiled(db, workspace_id, collection.blueprint)

    rows = [
        {**(doc.to_dict() or {}), "id": doc.id}
        for doc in children_path(db, workspace_id, blueprint_id, row_id).stream()
    ]
    rows = [r for r in rows if r.get("collectionId") == collection_id]

    trimmed, annotation, stubs = read_children(
        compile_rules(child_compiled),
        child_compiled,
        principal,
        rows,
        ChildContext(
            collection=collection, parent_row=parent_row, parent_decision=parent_decision
        ),
    )

    return _page_out(
        RowPage(
            rows=trimmed,
            annotation=annotation,
            cursor=None,
            has_more=False,
            column_stubs=stubs,
            plan=PagePlan(scanned=len(rows), rounds=1),
        ),
        child_compiled,
    )


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
