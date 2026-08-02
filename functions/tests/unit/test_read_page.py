"""Paging a permission-trimmed register.

The properties here all descend from one fact: the store cannot answer the
question the user asked, because whether a row is visible is decided after it is
fetched. Every test below is a way that fact bites.
"""

from __future__ import annotations

from typing import Any

import pytest

from lib.grammar.ast import parse
from lib.grammar.compile_query import QueryPlan
from lib.permissions.evaluate import compile_rules
from lib.permissions.model import Principal
from lib.rows.reader import (
    MAX_SCAN,
    InvalidCursor,
    PageRequest,
    SortSpec,
    decode_cursor,
    encode_cursor,
    read_page,
)
from tests.unit.test_write_path import BP


class ListSource:
    """A store that honours order, cursor and limit and nothing else.

    Filters are already checked by the query-compiler conformance suite; what
    these tests need is a store whose paging behaviour is exactly predictable.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[int] = []

    def fetch(
        self,
        plan: QueryPlan,
        *,
        order_by: tuple[str, str] | None,
        after: dict[str, Any] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(limit)
        start = 0
        if after is not None:
            ids = [r["id"] for r in self.rows]
            start = ids.index(after["id"]) + 1 if after["id"] in ids else 0
        return self.rows[start : start + limit]


def _rows(n: int, *, start: int = 0) -> list[dict[str, Any]]:
    return [
        {
            "id": f"r{i:05d}",
            "values": {
                "title": f"Row {i}",
                "amount": i,
                # Not indexed, and deliberately so: a filter on it cannot be
                # pushed down, which is what the residual tests need.
                "reference": f"PO-{i:05d}",
                "owner_rationale": "sealed",
            },
        }
        for i in range(start, start + n)
    ]


def _lt(field_id: str, value: Any) -> dict[str, Any]:
    return {"type": "binary", "op": "lt",
            "left": {"type": "field", "id": field_id},
            "right": {"type": "literal", "value": value}}


def _gte(field_id: str, value: Any) -> dict[str, Any]:
    return {"type": "binary", "op": "gte",
            "left": {"type": "field", "id": field_id},
            "right": {"type": "literal", "value": value}}


def _bp_with(rules: list[dict[str, Any]]) -> Any:
    from lib.blueprint.compile import compile_blueprint

    doc = BP.model_dump()
    doc["permissions"] = rules
    from lib.blueprint.model import Blueprint

    return compile_blueprint(Blueprint.model_validate(doc))


ALLOW_ALL = [{"principals": ["*"], "actions": ["read"], "effect": "allow"}]
MAYA = Principal(subject="u1", email="maya@unops.org", groups=frozenset({"staff"}))


def _read(rows: list[dict[str, Any]], rules: list[dict[str, Any]], **kw: Any) -> Any:
    compiled = _bp_with(rules)
    source = ListSource(rows)
    page = read_page(
        compiled, compile_rules(compiled), MAYA, source,
        PageRequest(**kw),
    )
    return page, source


# --- the cursor rule -----------------------------------------------------


def test_the_cursor_advances_past_withheld_rows() -> None:
    """The infinite loop this rule exists to prevent.

    A principal who may see nothing until row 5,000 hits the scan bound with an
    empty page. If the cursor were the last row *shown*, there is no such row,
    so the cursor would not advance — and the client would ask for the same
    first 5,000 documents forever, never reaching the rows it can actually see.
    """
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _lt("amount", MAX_SCAN)}
    ]
    page, _ = _read(_rows(MAX_SCAN + 100), rules, limit=10)

    assert page.rows == []
    assert page.has_more is True
    assert page.plan.scan_budget_exhausted is True
    # The store was read to the bound, and the cursor says so.
    assert decode_cursor(page.cursor)["id"] == f"r{MAX_SCAN - 1:05d}"


def test_the_page_after_the_scan_bound_reaches_the_visible_rows() -> None:
    """The other half of the same property: resuming from that cursor makes
    progress rather than re-reading what was already discarded."""
    rows = _rows(MAX_SCAN + 100)
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _lt("amount", MAX_SCAN)}
    ]
    first, _ = _read(rows, rules, limit=10)

    compiled = _bp_with(rules)
    second = read_page(
        compiled, compile_rules(compiled), MAYA, ListSource(rows),
        PageRequest(limit=10, cursor=first.cursor),
    )

    assert [r["id"] for r in second.rows] == [
        f"r{i:05d}" for i in range(MAX_SCAN, MAX_SCAN + 10)
    ]


def test_a_residual_filter_advances_the_cursor_too() -> None:
    """The same stranding, reached by the other exclusion path.

    A row can leave the page for two reasons — the user's filter could not be
    pushed down, or the permission decision withheld it — and both have to move
    the cursor. Advancing on only one of them means a view whose filter excludes
    a long run of rows never gets past it.
    """
    page, _ = _read(
        _rows(MAX_SCAN + 100), ALLOW_ALL, limit=10,
        filter=parse(_gte("reference", f"PO-{MAX_SCAN:05d}")),
    )

    assert page.rows == []
    assert page.plan.post_filtered is True
    assert page.plan.scan_budget_exhausted is True
    assert decode_cursor(page.cursor)["id"] == f"r{MAX_SCAN - 1:05d}"


def test_a_fully_withheld_register_that_ends_reports_the_end() -> None:
    """Distinct from the case above: here the store really is exhausted, so
    there is no cursor and the client stops rather than polling."""
    deny_all = [{"principals": ["*"], "actions": ["read"], "effect": "deny"}]
    page, _ = _read(_rows(50), deny_all, limit=10)

    assert page.rows == []
    assert page.annotation.withheld == 50
    assert page.has_more is False
    assert page.cursor is None


def test_resuming_from_a_cursor_returns_the_next_rows_exactly_once() -> None:
    rows = _rows(25)
    first, _ = _read(rows, ALLOW_ALL, limit=10)
    compiled = _bp_with(ALLOW_ALL)
    second = read_page(
        compiled, compile_rules(compiled), MAYA, ListSource(rows),
        PageRequest(limit=10, cursor=first.cursor),
    )

    seen = [r["id"] for r in first.rows] + [r["id"] for r in second.rows]
    assert seen == [f"r{i:05d}" for i in range(20)]
    assert len(seen) == len(set(seen))


def test_the_last_page_reports_no_cursor() -> None:
    page, _ = _read(_rows(5), ALLOW_ALL, limit=10)
    assert page.has_more is False
    assert page.cursor is None


# --- over-fetch and the scan bound ---------------------------------------


def test_the_reader_over_fetches_to_fill_a_page() -> None:
    """Asking the store for exactly a page would return a short page whenever
    anything is withheld, and the client cannot tell that from the end."""
    page, source = _read(_rows(100), ALLOW_ALL, limit=10)
    assert source.calls[0] > 10
    assert len(page.rows) == 10


def test_a_mostly_withheld_register_still_fills_a_page() -> None:
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _lt("amount", 90)}
    ]
    page, _ = _read(_rows(200), rules, limit=10)

    assert len(page.rows) == 10
    assert page.plan.rounds > 1  # one over-fetched round was not enough


def test_the_scan_bound_stops_a_full_register_scan_and_says_so() -> None:
    """A principal who can see one row in ten thousand must not turn every
    scroll into a full scan the register's owner pays for."""
    deny_all = [{"principals": ["*"], "actions": ["read"], "effect": "deny"}]
    page, _ = _read(_rows(MAX_SCAN + 500), deny_all, limit=10)

    assert page.plan.scanned <= MAX_SCAN
    assert page.plan.scan_budget_exhausted is True
    assert page.annotation.certainty == "estimated"
    assert page.annotation.ceiling == MAX_SCAN


def test_a_complete_page_reports_an_exact_count() -> None:
    page, _ = _read(_rows(30), ALLOW_ALL, limit=10)
    assert page.annotation.certainty == "exact"
    assert page.annotation.ceiling is None


# --- what the page says about itself -------------------------------------


def test_the_annotation_counts_withheld_rows_across_the_whole_scan() -> None:
    """Not just the last round. A count that reset per round would under-report
    by however many rounds it took."""
    rules = ALLOW_ALL + [
        {"principals": ["*"], "actions": ["read"], "effect": "deny",
         "row_condition": _lt("amount", 50)}
    ]
    page, _ = _read(_rows(80), rules, limit=10)

    assert page.annotation.visible == 10
    assert page.annotation.withheld == 50


def test_a_sort_with_no_slot_is_declined_with_a_reason_not_silently_ignored() -> None:
    """Sorting the fetched window in memory would look right on page one and be
    wrong on page two — worse than declining."""
    page, _ = _read(_rows(5), ALLOW_ALL, limit=10,
                    sort=(SortSpec(field_id="reference"),))

    assert page.plan.unsortable is not None
    assert "reference" in page.plan.unsortable
    assert "sort slot" in page.plan.unsortable


def test_a_sortable_field_uses_its_typed_slot() -> None:
    page, _ = _read(_rows(5), ALLOW_ALL, limit=10, sort=(SortSpec(field_id="amount"),))
    assert page.plan.unsortable is None


def test_an_unservable_filter_is_reported_as_post_filtered() -> None:
    """"This view cannot be served by the index" is actionable; a view that is
    simply slow is not."""
    page, _ = _read(_rows(5), ALLOW_ALL, limit=10, filter=parse(_gte("reference", "PO-1")))

    assert page.plan.post_filtered is True
    assert page.plan.reasons


def test_a_residual_filter_actually_excludes_rows() -> None:
    """A compiler that reported a residual and a reader that never applied it
    would return rows the user's filter excluded — silently.

    Filters on ``reference``, which is not indexed, so the term genuinely cannot
    be pushed down and the reader has to do the work.
    """
    page, _ = _read(_rows(10), ALLOW_ALL, limit=10, filter=parse(_gte("reference", "PO-00005")))

    assert page.plan.post_filtered is True
    assert [r["values"]["amount"] for r in page.rows] == [5, 6, 7, 8, 9]


def test_withheld_fields_render_as_stubs_on_every_returned_row() -> None:
    rules = [
        {"principals": ["*"], "actions": ["read"], "effect": "allow", "max_band": 0},
    ]
    page, _ = _read(_rows(3), rules, limit=10)

    assert page.rows
    for row in page.rows:
        assert row["values"]["owner_rationale"] == {"restricted": True}
    assert "owner_rationale" in page.column_stubs


def test_a_field_never_given_a_value_is_still_stubbed_when_restricted() -> None:
    """The case a value-map walk misses entirely.

    A row that has no value for a restricted field would emit no key at all, so
    the grid renders an ordinary empty cell where the whole column should read
    as withheld — and the reader learns "this column is restricted" only from
    the rows that happen to be populated.
    """
    rules = [{"principals": ["*"], "actions": ["read"], "effect": "allow", "max_band": 0}]
    rows = [{"id": "r1", "values": {"title": "No rationale recorded", "amount": 1}}]
    page, _ = _read(rows, rules, limit=10)

    assert page.rows[0]["values"]["owner_rationale"] == {"restricted": True}
    assert "owner_rationale" in page.column_stubs


# --- the cursor is opaque ------------------------------------------------


def test_a_cursor_round_trips() -> None:
    position = {"id": "r1", "slot": "num0", "value": 12}
    assert decode_cursor(encode_cursor(position)) == position


def test_a_malformed_cursor_is_an_error_not_a_silent_restart() -> None:
    """Restarting silently means a client with a stale cursor re-reads page one
    forever while believing it is making progress."""
    with pytest.raises(InvalidCursor):
        decode_cursor("not-base64-at-all!!")
    with pytest.raises(InvalidCursor):
        decode_cursor(encode_cursor({"nothing": "useful"}))


def test_the_page_size_is_bounded() -> None:
    """An unbounded limit is a scan with extra steps."""
    assert PageRequest(limit=10_000).bounded_limit() == 500
    assert PageRequest(limit=0).bounded_limit() == 1
