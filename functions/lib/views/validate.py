"""Checking a saved view against the Blueprint it belongs to.

The point is to refuse or warn *at save time*, when the author is present and
can fix it, rather than at open time when a colleague sees an empty grid. An
empty grid is indistinguishable from a permission denial, and users conclude the
wrong one — "I don't have access to this any more" is a much more expensive
wrong conclusion than "this filter is broken".

Two severities, and the distinction matters:

**Errors refuse the save.** A filter referencing a field that does not exist can
never return anything correct.

**Warnings save it anyway and say so.** A sort on a field with no typed slot is
the case that matters here: it is *legal*, it is *user-visible* as "you cannot
sort by this column", and it is caused by a Blueprint-level slot budget the view
author does not control. Refusing it would make one steward's field ordering
decide whether another can save a view.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING

from lib.grammar.analyse import analyse
from lib.grammar.ast import parse
from lib.views.model import SavedView

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint


@dataclass(frozen=True, slots=True)
class ViewIssue:
    code: str
    message: str
    field_id: str | None = None


@dataclass(slots=True)
class ViewReport:
    errors: list[ViewIssue] = dc_field(default_factory=list)
    warnings: list[ViewIssue] = dc_field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        lines = [f"error {i.code}: {i.message}" for i in self.errors]
        lines += [f"warning {i.code}: {i.message}" for i in self.warnings]
        return "\n".join(lines) or "ok"


def validate_view(view: SavedView, compiled: CompiledBlueprint) -> ViewReport:
    report = ViewReport()

    if view.blueprint_id != compiled.id:
        report.errors.append(
            ViewIssue("blueprint_mismatch", f"This view belongs to {view.blueprint_id!r}")
        )
        return report

    known = set(compiled.fields)

    if view.filter is not None:
        try:
            analysis = analyse(parse(view.filter))
        except (ValueError, KeyError, TypeError) as exc:
            # A malformed AST is refused here rather than at open time, where it
            # would surface as a 500 to whoever the view was shared with.
            report.errors.append(ViewIssue("bad_filter", f"The filter is not valid: {exc}"))
            return report

        for field_id in sorted(analysis.fields):
            if field_id not in known:
                report.errors.append(
                    ViewIssue(
                        "unknown_field",
                        f"The filter refers to {field_id!r}, which is not a field on "
                        f"{compiled.blueprint.name}. It may have been removed since this "
                        "view was saved.",
                        field_id,
                    )
                )

        if analysis.required_scope.value != "row":
            # A view is opened by whoever holds the link. A filter that reads the
            # acting principal would mean the same saved view is a different
            # query per viewer — which is exactly the confusion between "a view"
            # and "a permission" this design refuses. Scoping by principal is
            # what PM-2a allow-lists are for, on the rule, where it is audited.
            report.errors.append(
                ViewIssue(
                    "subject_in_filter",
                    "A view's filter cannot read the signed-in user. Views are shared "
                    "and grant nothing; per-person scoping belongs in a permission "
                    "rule, where it is reviewable.",
                )
            )

    for sort in view.sort:
        cf = compiled.field(sort.field_id)
        if cf is None:
            report.errors.append(
                ViewIssue("unknown_field", f"Cannot sort by {sort.field_id!r}: no such field", sort.field_id)
            )
        elif cf.sort_slot is None:
            # A warning, not an error. See the module docstring: the cause is a
            # Blueprint-level slot budget this author does not control.
            report.warnings.append(
                ViewIssue(
                    "unsortable",
                    f"{cf.definition.label} has no server-side sort slot, so rows will "
                    f"come back in their default order. Slots in use: "
                    f"{compiled.index_plan.slot_pressure}.",
                    sort.field_id,
                )
            )

    for column in view.columns:
        if column.field_id not in known:
            report.warnings.append(
                ViewIssue(
                    "unknown_column",
                    f"{column.field_id!r} is no longer a field and will not be shown.",
                    column.field_id,
                )
            )

    if view.group_by is not None:
        cf = compiled.field(view.group_by)
        if cf is None:
            report.errors.append(
                ViewIssue("unknown_field", f"Cannot group by {view.group_by!r}: no such field")
            )
        else:
            # Both checks run. They are independent facts about the same field
            # and an `elif` reports whichever happens to be tested first — which
            # is how the author of a restricted, unindexed grouping field learns
            # about the indexing and never about the disclosure.
            if cf.eq_token_prefix is None:
                report.warnings.append(
                    ViewIssue(
                        "ungroupable",
                        f"{cf.definition.label} is not declared filterable, so grouping is "
                        "computed over the loaded window rather than the whole register.",
                        view.group_by,
                    )
                )
            if cf.is_restricted:
                # Not a refusal: the reader's Decision still governs. But a group
                # header carries the value, and a reader who may not see the value
                # would get it in the header — so the caller must trim group labels
                # the same way it trims cells, and this is where that is flagged.
                report.warnings.append(
                    ViewIssue(
                        "restricted_grouping",
                        f"{cf.definition.label} is a restricted field. Readers without access "
                        "will see a single withheld group rather than its values.",
                        view.group_by,
                    )
                )

    return report
