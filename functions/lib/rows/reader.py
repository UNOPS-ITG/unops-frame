"""The read path: fetch, evaluate, trim, page.

Reading is harder than writing here, and for one reason: **the store cannot
serve the question**. A page of 100 rows the *user* may see is not a page of 100
rows the *store* can find, because the permission decision is made per row after
the fetch. Everything below follows from that.

**Over-fetch, bounded, and say when the bound was hit.** To fill a page the
reader fetches more than a page and keeps going until it has enough visible rows
or it reaches ``MAX_SCAN``. Unbounded would mean a register whose rows are almost
all withheld turns one page request into a full scan. Bounded-and-silent would
mean the client shows "no more rows" when the truth is "we stopped looking" —
so the bound being hit is reported, and the count's certainty drops to
``estimated``.

**The cursor is the last document FETCHED, never the last row SHOWN.** This is
the whole reason the two are tracked separately. If a page's last four documents
are all withheld, the last shown row is the fifth-from-last; resuming from it
re-fetches those four, re-evaluates them, discards them again, and returns the
same cursor. A page where *every* document is withheld returns zero rows and an
unchanged cursor, and the client loops forever on a register it has partial
access to — which is the common case, not an edge case.

**Residuals are counted against the scan budget, not hidden.** A filter the
store cannot serve becomes a post-filter, and a post-filter that runs over an
unbounded fetch is a scan wearing a query's clothes. ``compile_query`` already
reports what it could not push down; the reader charges it.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any, Protocol

from lib.grammar.ast import Expr
from lib.grammar.compile_query import QueryPlan, compile_query
from lib.grammar.evaluate import Context, Subject, matches
from lib.permissions.evaluate import CompiledRuleSet, evaluate_row
from lib.permissions.model import Annotation, Decision, Principal
from lib.permissions.trim import trim_page

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

OVERFETCH_FACTOR = 3
"""How much more than a page to ask the store for per round.

Three rather than two because a register where a third of rows are withheld is
ordinary at UNOPS, and rather than ten because each round's cost is real and an
over-eager first fetch penalises the common fully-visible case.
"""

MAX_SCAN = 5_000
"""Documents one page request may examine before giving up.

Not a performance tuning knob — a denial-of-service bound. Without it, a
principal who can see one row in ten thousand turns every scroll into a full
register scan, and the register's owner pays for it.
"""


class RowSource(Protocol):
    """Where rows come from. A protocol so the paging logic is testable.

    Deliberately narrow: the store is asked for documents in an order, after a
    cursor, up to a limit. Everything else — permission evaluation, trimming,
    residual filtering, counting — happens above it, which is what keeps the
    single permission evaluator single.
    """

    def fetch(
        self,
        plan: QueryPlan,
        *,
        order_by: tuple[str, str] | None,
        after: dict[str, Any] | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class SortSpec:
    field_id: str
    direction: str = "asc"


@dataclass(frozen=True, slots=True)
class PageRequest:
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None
    filter: Expr | None = None
    sort: tuple[SortSpec, ...] = ()

    def bounded_limit(self) -> int:
        return max(1, min(self.limit, MAX_PAGE_SIZE))


@dataclass(slots=True)
class PagePlan:
    """Why this page cost what it did. Returned, not logged.

    A view that is expensive should be able to say so in the UI — "this filter
    cannot be served by the index" is actionable, "loading…" forever is not.
    """

    store_filters: int = 0
    post_filtered: bool = False
    reasons: list[str] = dc_field(default_factory=list)
    scanned: int = 0
    rounds: int = 0
    scan_budget_exhausted: bool = False
    unsortable: str | None = None


@dataclass(slots=True)
class RowPage:
    rows: list[dict[str, Any]]
    annotation: Annotation
    cursor: str | None
    has_more: bool
    column_stubs: frozenset[str]
    plan: PagePlan


def read_page(
    compiled: CompiledBlueprint,
    rule_set: CompiledRuleSet,
    principal: Principal,
    source: RowSource,
    request: PageRequest,
    *,
    parent_decision: Decision | None = None,
    parent_row: dict[str, Any] | None = None,
) -> RowPage:
    """One page of rows, as this principal may see them."""
    limit = request.bounded_limit()
    query_plan = compile_query(request.filter, compiled, principal.allow_lists)
    order_by, unsortable = _resolve_order(compiled, request.sort)

    page = PagePlan(
        store_filters=len(query_plan.filters),
        post_filtered=query_plan.needs_post_filter,
        reasons=list(query_plan.reasons),
        unsortable=unsortable,
    )

    visible: list[dict[str, Any]] = []
    decisions: list[Decision] = []
    withheld = 0
    after = decode_cursor(request.cursor)
    last_fetched: dict[str, Any] | None = None
    exhausted = False

    while len(visible) < limit and page.scanned < MAX_SCAN:
        want = min((limit - len(visible)) * OVERFETCH_FACTOR, MAX_SCAN - page.scanned)
        batch = source.fetch(query_plan, order_by=order_by, after=after, limit=want)
        page.rounds += 1
        if not batch:
            exhausted = True
            break

        consumed_whole_batch = True
        for row in batch:
            if len(visible) >= limit:
                # The page filled part-way through the batch. The rest of it is
                # unread, so the store is emphatically NOT exhausted — however
                # short the batch was. Concluding otherwise here is how a
                # register of 25 rows served in pages of 10 reports "no more"
                # after the first page.
                consumed_whole_batch = False
                break

            page.scanned += 1
            # Tracked on EVERY document, before any filter or permission check.
            # The cursor's whole job is "where the store got to", and a cursor
            # that only advances past rows the reader kept cannot express that.
            last_fetched = row

            if query_plan.residual is not None and not _residual_holds(
                query_plan.residual, row, principal
            ):
                continue

            decision = evaluate_row(
                rule_set, principal, row,
                compiled=compiled,
                parent_decision=parent_decision,
                parent_row=parent_row,
            )
            if not decision.visible:
                withheld += 1
                continue

            visible.append(row)
            decisions.append(decision)

        # A short batch means the end of the register only if we read all of it.
        if consumed_whole_batch and len(batch) < want:
            exhausted = True
            break
        after = _cursor_values(last_fetched, order_by)

    page.scan_budget_exhausted = page.scanned >= MAX_SCAN and not exhausted

    trimmed, annotation, column_stubs = trim_page(
        visible, decisions,
        scope="page",
        # A page that stopped at the scan bound is not a page that reached the
        # end. Reporting `exact` here would be a lie the client cannot detect.
        certainty="estimated" if page.scan_budget_exhausted else "exact",
        ceiling=MAX_SCAN if page.scan_budget_exhausted else None,
    )
    annotation = Annotation(
        visible=annotation.visible,
        withheld=withheld,
        scope=annotation.scope,
        certainty=annotation.certainty,
        ceiling=annotation.ceiling,
    )

    has_more = not exhausted
    return RowPage(
        rows=trimmed,
        annotation=annotation,
        cursor=encode_cursor(_cursor_values(last_fetched, order_by)) if has_more else None,
        has_more=has_more,
        column_stubs=column_stubs,
        plan=page,
    )


def _resolve_order(
    compiled: CompiledBlueprint, sort: tuple[SortSpec, ...]
) -> tuple[tuple[str, str] | None, str | None]:
    """Map a requested sort onto a typed slot, or decline it and say why.

    Slots are the scarce resource the projection design trades against index
    count, and running out is a product constraint a user feels as "I cannot
    sort by this column". Falling back to an in-memory sort of the page would be
    worse than declining: it sorts the fetched window, not the register, and
    looks correct until the second page.
    """
    if not sort:
        return ("__name__", "asc"), None

    first = sort[0]
    cf = compiled.field(first.field_id)
    if cf is None:
        return ("__name__", "asc"), f"{first.field_id}: no such field"
    if cf.sort_slot is None:
        return (
            ("__name__", "asc"),
            f"{first.field_id}: no typed sort slot is assigned, so the store cannot "
            f"order by it ({compiled.index_plan.slot_pressure})",
        )
    return (cf.sort_slot, "desc" if first.direction == "desc" else "asc"), None


def _residual_holds(residual: Expr, row: dict[str, Any], principal: Principal) -> bool:
    ctx = Context(
        row=row.get("values", row) if "values" in row else row,
        subject=Subject(
            email=principal.email, subject=principal.subject, groups=principal.groups
        ),
        allow_lists=principal.allow_lists,
    )
    return matches(residual, ctx)


def _cursor_values(
    row: dict[str, Any] | None, order_by: tuple[str, str] | None
) -> dict[str, Any] | None:
    """The store position of one document.

    Carries the ordered slot value as well as the id because Firestore's
    ``start_after`` needs a value for every order-by clause; an id alone is only
    sufficient when the id is the sort.
    """
    if row is None:
        return None
    position: dict[str, Any] = {"id": row.get("id")}
    if order_by and order_by[0] != "__name__":
        position["slot"] = order_by[0]
        position["value"] = row.get(order_by[0])
    return position


def encode_cursor(position: dict[str, Any] | None) -> str | None:
    """Opaque to the client, on purpose.

    A cursor a client can read is a cursor a client will construct, and a
    constructed cursor is an unvalidated store position — which is how a
    pagination parameter becomes a way to ask for someone else's rows.
    """
    if position is None:
        return None
    raw = json.dumps(position, separators=(",", ":"), sort_keys=True, default=str)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except (ValueError, binascii.Error) as exc:
        raise InvalidCursor(str(exc)) from exc
    if not isinstance(decoded, dict) or "id" not in decoded:
        raise InvalidCursor("cursor does not name a document")
    return decoded


class InvalidCursor(ValueError):
    """A 400, never a silent restart from the beginning.

    Restarting silently means a client with a stale cursor re-reads page one
    forever while believing it is making progress.
    """
