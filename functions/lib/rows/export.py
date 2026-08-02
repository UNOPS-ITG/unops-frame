"""Export.

An export is a *read*, and it is the read most likely to leave the building. Two
consequences that are not optional:

**A withheld field exports as withheld, never as blank.** A blank cell in a
spreadsheet reads as "no value recorded", which is a different and wrong fact —
and unlike the grid, a spreadsheet has no tooltip to correct it. It is also the
version someone forwards.

**The withheld row count travels with the file.** PM-5 requires the annotation
to be stated, and a CSV has nowhere to put one except in the data. So the export
carries a trailing note rather than pretending the file is the whole register:
a reader who sums an exported column and reports the total must be able to see
that the total is partial.

Export is also a distinct action (``Action.EXPORT``) and an audited one. A user
who may read a register on screen has not thereby been granted the right to take
a copy of it home.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Any

from lib.permissions.model import Annotation

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint

WITHHELD_CELL = "(withheld)"


def to_csv(
    rows: list[dict[str, Any]],
    compiled: CompiledBlueprint,
    annotation: Annotation,
    *,
    columns: tuple[str, ...] | None = None,
) -> str:
    """Render trimmed rows as CSV.

    ``rows`` are already trimmed — this function applies no permission logic and
    must not, because a second place that decides what a reader may see is a
    second place that can be wrong.
    """
    field_ids = columns or tuple(compiled.fields)
    known = [fid for fid in field_ids if fid in compiled.fields]

    buffer = io.StringIO()
    # QUOTE_ALL, not QUOTE_MINIMAL: a value beginning with =, +, - or @ is
    # executed as a formula by Excel and Sheets on open, and quoting is the part
    # of the mitigation that survives a round trip through both.
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")

    writer.writerow([compiled.fields[fid].definition.label for fid in known])

    for row in rows:
        values = row.get("values", {})
        writer.writerow([_cell(values.get(fid), compiled, fid) for fid in known])

    if annotation.withheld > 0:
        # In the data, because a CSV has nowhere else to put it. Anyone who sums
        # a column of this file and reports the total needs to be able to see
        # that the total is partial.
        writer.writerow([])
        writer.writerow(
            [
                f"{annotation.withheld} further row(s) exist that you do not have "
                f"permission to see. This export covers {annotation.visible} of "
                f"{annotation.total}."
            ]
        )

    return buffer.getvalue()


def _cell(value: Any, compiled: CompiledBlueprint, field_id: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and value.get("restricted") is True:
        return WITHHELD_CELL
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(_label(str(v), compiled, field_id) for v in value)
    if isinstance(value, str):
        return _escape_formula(_label(value, compiled, field_id))
    return str(value)


def _label(value: str, compiled: CompiledBlueprint, field_id: str) -> str:
    """A select field's label, not its stored key.

    The key exists so renaming a label does not rewrite every row; it is an
    internal identifier the user never chose and should not be exported.
    """
    cf = compiled.field(field_id)
    if cf is None or not cf.definition.options:
        return value
    for option in cf.definition.options:
        if option.key == value:
            return option.label
    return value


def _escape_formula(value: str) -> str:
    """Neutralise CSV formula injection.

    A cell starting with ``=``, ``+``, ``-``, ``@``, tab or CR is evaluated on
    open by Excel and Sheets. Frame's own data is trimmed and validated, but the
    values in it were typed by users and a register is exactly the kind of file
    that gets mailed to someone outside the organisation.

    Prefixed with an apostrophe rather than stripped, because the leading
    character may be meaningful — an account code, a negative number entered as
    text — and silently altering exported data is its own defect.
    """
    if value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return f"'{value}"
    return value
