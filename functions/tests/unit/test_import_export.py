"""Import and export.

Import is where BP-4's claim is either true or a comment: a row created by a
file must be indistinguishable from a row someone typed, and must have been
refused for the same reasons. Export is the read most likely to leave the
building, so what it says about what it does not contain matters more than
anywhere else.
"""

from __future__ import annotations

from typing import Any

import pytest

from lib.permissions.model import Action, Annotation, Decision
from lib.rows.export import WITHHELD_CELL, to_csv
from lib.rows.importer import (
    CHUNK_ROWS,
    MAX_IMPORT_ROWS,
    build_chunks,
    parse_csv,
    plan_import,
)
from lib.rows.writer import WriteContext
from tests.unit.test_write_path import COMPILED

ALL = frozenset(COMPILED.fields)
FULL = Decision(
    allowed=frozenset({Action.READ, Action.CREATE, Action.IMPORT}),
    readable_fields=ALL,
    writable_fields=ALL,
)
BAND_LIMITED = Decision(
    allowed=frozenset({Action.READ, Action.CREATE, Action.IMPORT}),
    readable_fields=ALL - {"owner_rationale"},
    writable_fields=ALL - {"owner_rationale"},
    restricted_fields=frozenset({"owner_rationale"}),
)
CTX = WriteContext(workspace_id="ws1", blueprint_id="risk", actor="maya", channel="import")


# --- parsing --------------------------------------------------------------


def test_columns_match_on_label_as_well_as_field_id() -> None:
    """A file exported from Frame carries ids; a file typed by a human carries
    labels. Refusing the second means every import starts with a rename."""
    rows, unmapped, errors = parse_csv("Title,Amount\nLate filing,500\n", COMPILED)

    assert errors == []
    assert rows == [{"title": "Late filing", "amount": 500}]
    assert unmapped == []


def test_an_unmatched_column_is_reported_not_silently_dropped() -> None:
    """A mis-exported file whose columns silently vanish produces rows that look
    complete and are not."""
    _, unmapped, _ = parse_csv("title,invented\nx,y\n", COMPILED)
    assert unmapped == ["invented"]


def test_a_select_accepts_its_label_as_well_as_its_key() -> None:
    """A file a human typed says "Conduct", not "conduct"."""
    rows, _, _ = parse_csv("title,risk_type\nx,Conduct\n", COMPILED)
    assert rows[0]["risk_type"] == "conduct"


def test_a_number_that_will_not_parse_keeps_the_typed_text() -> None:
    """So validation reports "must be a number" against the value the user
    actually typed. Nulling it silently produces "is required" against a cell
    that plainly is not empty."""
    rows, _, _ = parse_csv("title,amount\nx,not a number\n", COMPILED)
    assert rows[0]["amount"] == "not a number"


def test_thousands_separators_are_accepted() -> None:
    rows, _, _ = parse_csv('title,amount\nx,"1,250"\n', COMPILED)
    assert rows[0]["amount"] == 1250


def test_blank_lines_are_skipped_not_imported_as_empty_rows() -> None:
    rows, _, _ = parse_csv("title,amount\nx,1\n\n\ny,2\n", COMPILED)
    assert len(rows) == 2


def test_an_empty_file_is_an_error_rather_than_a_successful_no_op() -> None:
    _, _, errors = parse_csv("", COMPILED)
    assert errors[0].code == "empty"


# --- the same validation as every other channel --------------------------


def test_a_row_that_could_not_be_typed_cannot_be_imported() -> None:
    """The defect class this module exists to prevent: "it validates in the grid
    but not on import"."""
    plan = plan_import(
        "title,amount\nOK,100\n,200\nAlso ok,5000000\n", COMPILED, FULL
    )

    codes = {(e.line, e.code) for e in plan.errors}
    assert (3, "required") in codes   # blank title on line 3
    assert (4, "max") in codes        # amount over the declared maximum
    assert len(plan.rows) == 1


def test_error_lines_are_1_based_and_include_the_header() -> None:
    """So they match what the user sees in Excel. A 0-based index against a file
    the user is looking at turns a two-minute fix into a hunt."""
    plan = plan_import("title,amount\nfine,1\n,2\n", COMPILED, FULL)
    assert [e.line for e in plan.errors] == [3]


def test_an_unwritable_field_is_refused_on_import_too() -> None:
    """A field the importer may not write is not quietly dropped: the row they
    believed they imported is not the row that exists."""
    plan = plan_import(
        "title,owner_rationale\nx,secret\n", COMPILED, BAND_LIMITED
    )
    assert [e.code for e in plan.errors] == ["forbidden_field"]
    assert plan.rows == []


def test_import_needs_the_import_or_create_verb() -> None:
    """Bulk creation bypasses the per-row attention create assumes. A team that
    may add risks one at a time has not thereby been granted the right to paste
    in four thousand."""
    read_only = Decision(allowed=frozenset({Action.READ}), readable_fields=ALL)
    plan = plan_import("title\nx\n", COMPILED, read_only)
    assert [e.code for e in plan.errors] == ["forbidden"]


def test_defaults_apply_on_import_exactly_as_on_create() -> None:
    plan = plan_import("title\nx\n", COMPILED, FULL)
    assert plan.ok
    assert "title" in plan.rows[0]


def test_planning_touches_no_store() -> None:
    """A dry run by construction. An import that reports its failures only after
    writing half the file is one the user cannot safely retry."""
    plan = plan_import("title,amount\nx,1\ny,2\n", COMPILED, FULL)
    assert plan.ok
    assert len(plan.rows) == 2
    assert plan.total_lines == 2


def test_a_file_beyond_the_row_cap_is_refused_rather_than_half_applied() -> None:
    text = "title\n" + "".join(f"row {i}\n" for i in range(MAX_IMPORT_ROWS + 5))
    plan = plan_import(text, COMPILED, FULL)
    assert any(e.code == "too_large" for e in plan.errors)


# --- chunking -------------------------------------------------------------


def test_rows_are_chunked_to_stay_inside_a_transaction() -> None:
    text = "title\n" + "".join(f"row {i}\n" for i in range(CHUNK_ROWS + 50))
    plan = plan_import(text, COMPILED, FULL)
    chunks = build_chunks(plan, COMPILED, CTX)

    assert len(chunks) == 2
    assert all(c.commit_size <= 500 for c in chunks)


def test_one_audit_entry_per_chunk_not_per_row() -> None:
    """A 5,000-row import writing 5,000 change entries makes the activity drawer
    useless for exactly the register someone just changed most."""
    text = "title\n" + "".join(f"row {i}\n" for i in range(10))
    chunks = build_chunks(plan_import(text, COMPILED, FULL), COMPILED, CTX)

    assert len(chunks) == 1
    assert chunks[0].audit.detail["importedRows"] == 10
    assert chunks[0].audit.action == "row.import"
    assert chunks[0].audit.channel == "import"


def test_every_imported_row_emits_its_own_event() -> None:
    """Consumers act per row. One event for a batch would mean the search index
    and the replica each have to guess which rows moved."""
    text = "title\n" + "".join(f"row {i}\n" for i in range(10))
    chunks = build_chunks(plan_import(text, COMPILED, FULL), COMPILED, CTX)

    assert len(chunks[0].envelope.events) == 10
    assert {e.event_type.value for e in chunks[0].envelope.events} == {"frame.row.created"}


def test_imported_rows_carry_the_index_projection() -> None:
    """Otherwise imported rows exist and no saved view finds them — which reads
    to the user as the import having silently failed."""
    chunks = build_chunks(
        plan_import("title,risk_type\nx,conduct\n", COMPILED, FULL), COMPILED, CTX
    )
    _, document = chunks[0].documents[0]
    assert "fld_risk_type=conduct" in document["eq"]


def test_imported_row_ids_are_opaque_and_unique() -> None:
    text = "title\n" + "".join(f"row {i}\n" for i in range(50))
    chunks = build_chunks(plan_import(text, COMPILED, FULL), COMPILED, CTX)
    ids = {row_id for c in chunks for row_id, _ in c.documents}
    assert len(ids) == 50


# --- export ---------------------------------------------------------------


def _rows(*values: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"id": f"r{i}", "values": v} for i, v in enumerate(values)]


def test_a_withheld_field_exports_as_withheld_never_as_blank() -> None:
    """A blank cell in a spreadsheet reads as "no value recorded" — a different
    and wrong fact, in the version someone forwards."""
    csv_text = to_csv(
        _rows({"title": "Late filing", "owner_rationale": {"restricted": True}}),
        COMPILED,
        Annotation(visible=1, withheld=0),
    )
    assert WITHHELD_CELL in csv_text


def test_the_withheld_row_count_travels_with_the_file() -> None:
    """A reader who sums an exported column and reports the total has to be able
    to see that the total is partial."""
    csv_text = to_csv(
        _rows({"title": "x"}), COMPILED, Annotation(visible=1, withheld=12)
    )
    assert "12 further row(s)" in csv_text
    assert "1 of 13" in csv_text


def test_a_complete_export_carries_no_note() -> None:
    csv_text = to_csv(_rows({"title": "x"}), COMPILED, Annotation(visible=1, withheld=0))
    assert "further row" not in csv_text


def test_a_formula_cell_is_neutralised() -> None:
    """A cell starting with = is executed on open by Excel and Sheets, and a
    register is exactly the kind of file that gets mailed outside the
    organisation."""
    csv_text = to_csv(
        _rows({"title": '=cmd|" /C calc"!A0'}), COMPILED, Annotation(visible=1, withheld=0)
    )
    assert "\"'=cmd" in csv_text


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_every_dangerous_prefix_is_neutralised(prefix: str) -> None:
    csv_text = to_csv(
        _rows({"title": f"{prefix}danger"}), COMPILED, Annotation(visible=1, withheld=0)
    )
    assert f"\"'{prefix}danger\"" in csv_text


def test_a_neutralised_value_is_prefixed_rather_than_stripped() -> None:
    """The leading character may be meaningful — an account code, a negative
    number entered as text — and silently altering exported data is its own
    defect."""
    csv_text = to_csv(
        _rows({"title": "-1000"}), COMPILED, Annotation(visible=1, withheld=0)
    )
    assert "-1000" in csv_text


def test_a_select_exports_its_label_not_its_key() -> None:
    csv_text = to_csv(
        _rows({"title": "x", "risk_type": "conduct"}),
        COMPILED,
        Annotation(visible=1, withheld=0),
    )
    assert "Conduct" in csv_text


def test_the_header_uses_labels_so_the_file_round_trips() -> None:
    """parse_csv matches on label as well as id, so an exported file re-imports
    without a rename."""
    csv_text = to_csv(_rows({"title": "x"}), COMPILED, Annotation(visible=1, withheld=0))
    header = csv_text.splitlines()[0]
    assert "Title" in header

    rows, unmapped, errors = parse_csv(csv_text.split("\n\n")[0], COMPILED)
    assert unmapped == []
    assert errors == []
    assert rows[0]["title"] == "x"
