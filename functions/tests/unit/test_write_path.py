"""The single write path.

The properties here are the ones whose absence is a data-loss bug rather than a
usability complaint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from lib.blueprint.compile import compile_blueprint
from lib.blueprint.model import (
    Blueprint,
    FieldDef,
    SelectOption,
    Tier,
    ValidationRule,
    ViewDefaults,
)
from lib.permissions.model import Action, Decision, Principal
from lib.rows.audit import WITHHELD, AuditClass, diff, trim_deltas
from lib.rows.outbox import EventType, assert_no_row_bodies, build_envelope
from lib.rows.writer import (
    WriteContext,
    WriteRejected,
    detect_conflicts,
    prepare_write,
)

BP = Blueprint.model_validate(
    {
        "id": "risk",
        "name": "Risks",
        "workspace_id": "ws1",
        "tier": Tier.TEAM,
        "fields": [
            FieldDef(id="title", label="Title", type="text", variant="single", required=True, indexed=True),
            FieldDef(
                id="risk_type", label="Risk type", type="single_select", indexed=True,
                options=[SelectOption(key="conduct", label="Conduct"), SelectOption(key="fraud", label="Fraud")],
            ),
            FieldDef(
                id="amount", label="Amount", type="number", variant="decimal", indexed=True,
                validation=ValidationRule(min=0, max=1_000_000),
            ),
            FieldDef(id="reference", label="Reference", type="text", variant="single", set_once=True),
            FieldDef(id="owner_rationale", label="Rationale", type="text", variant="long", sensitivity=2),
        ],
        "view_defaults": ViewDefaults(title_field="title"),
    }
)
COMPILED = compile_blueprint(BP)
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
CTX = WriteContext(workspace_id="ws1", blueprint_id="risk", actor="maya", channel="grid", correlation_id="c1")

ALL_FIELDS = frozenset(COMPILED.fields)
FULL = Decision(
    allowed=frozenset({Action.READ, Action.CREATE, Action.UPDATE}),
    readable_fields=ALL_FIELDS,
    writable_fields=ALL_FIELDS,
)
# Band-scoped: may not read or write the restricted field.
LIMITED = Decision(
    allowed=frozenset({Action.READ, Action.UPDATE}),
    readable_fields=ALL_FIELDS - {"owner_rationale"},
    writable_fields=ALL_FIELDS - {"owner_rationale"},
    restricted_fields=frozenset({"owner_rationale"}),
)


def _stored(**values: Any) -> dict[str, Any]:
    return {
        "id": "r1",
        "values": {"title": "Late filing", "amount": 20_000, "owner_rationale": "sealed", **values},
        "fieldVersions": {"title": 1, "amount": 1, "owner_rationale": 1},
        "createdAt": NOW,
        "createdBy": "maya",
    }


# --- the restricted-stub write contract ----------------------------------


def test_a_restricted_stub_is_never_accepted_as_a_value() -> None:
    """Not hypothetical: Frappe shipped the same masking mechanism and
    immediately hit a client posting the placeholder back on save, overwriting
    real data."""
    with pytest.raises(WriteRejected) as exc:
        prepare_write(
            COMPILED, CTX, row_id="r1",
            submitted_values={"owner_rationale": {"restricted": True}},
            stored=_stored(), decision=FULL, now=NOW,
        )
    assert exc.value.code == "forbidden_fields"
    assert "owner_rationale" in str(exc.value)


def test_writing_an_unwritable_field_is_refused_by_name_not_silently_reverted() -> None:
    """A client that believes it wrote something it did not is worse off than
    one that got an error."""
    with pytest.raises(WriteRejected) as exc:
        prepare_write(
            COMPILED, CTX, row_id="r1",
            submitted_values={"owner_rationale": "leaked"},
            stored=_stored(), decision=LIMITED, now=NOW,
        )
    assert "owner_rationale" in str(exc.value)


def test_a_creator_cannot_populate_a_field_they_may_not_write() -> None:
    """The escalation that field scoping on update alone leaves open.

    Someone who may not write a restricted field on an existing row could
    otherwise set it on a NEW one — reachable by anyone able to add a row at
    all, and leaving no trace, because the value is simply there from the start.
    """
    with pytest.raises(WriteRejected) as exc:
        prepare_write(
            COMPILED, CTX, row_id=None,
            submitted_values={"title": "New", "owner_rationale": "fabricated"},
            stored=None,
            decision=Decision(
                allowed=frozenset({Action.READ, Action.CREATE}),
                readable_fields=ALL_FIELDS - {"owner_rationale"},
                writable_fields=ALL_FIELDS - {"owner_rationale"},
                restricted_fields=frozenset({"owner_rationale"}),
            ),
            now=NOW,
        )
    assert exc.value.code == "forbidden_fields"
    assert "owner_rationale" in str(exc.value)


def test_a_create_grant_makes_its_fields_writable() -> None:
    """The other half: reading writability from UPDATE alone leaves a
    create-only grant unable to write anything, which is why the check used to
    be skipped on create in the first place."""
    from lib.blueprint.model import Blueprint
    from lib.permissions.evaluate import compile_rules, evaluate_row

    doc = BP.model_dump()
    doc["permissions"] = [
        {"principals": ["*"], "actions": ["read", "create"], "effect": "allow"}
    ]
    compiled = compile_blueprint(Blueprint.model_validate(doc))
    decision = evaluate_row(
        compile_rules(compiled),
        Principal(subject="u1", email="maya@unops.org"),
        {"values": {}},
        compiled=compiled,
    )

    assert decision.writable_fields == frozenset(compiled.fields)


def test_an_unwritable_fields_stored_value_survives_a_partial_write() -> None:
    """The restore-before-validate step: a writer who cannot see a field must
    not blank it by omission."""
    pending, result = prepare_write(
        COMPILED, CTX, row_id="r1",
        submitted_values={"title": "Updated"},
        stored=_stored(), decision=LIMITED, now=NOW,
    )
    assert result.values["owner_rationale"] == "sealed"
    assert result.changed_fields == ("title",)


# --- field-scoped versions and per-cell conflict -------------------------


def test_only_changed_fields_have_their_version_bumped() -> None:
    """A concurrent writer touching a different cell must not invalidate this
    one — which is the whole reason writes are field-scoped."""
    _, result = prepare_write(
        COMPILED, CTX, row_id="r1",
        submitted_values={"title": "Updated"},
        stored=_stored(), decision=FULL, now=NOW,
    )
    assert result.field_versions["title"] == 2
    assert result.field_versions["amount"] == 1


def test_concurrent_edits_to_different_cells_do_not_conflict() -> None:
    """GR-8 forbids document-level locking. A whole-row save cannot express
    this, and one of the two edits would be lost."""
    stored_versions = {"title": 2, "amount": 1}
    conflicts = detect_conflicts({"amount": 1}, stored_versions, changed=("amount",))
    assert conflicts == ()


def test_a_stale_edit_to_the_same_cell_is_reported_by_field() -> None:
    """The loser is told which field it lost, so the client can offer the value
    back rather than silently discarding it."""
    stored_versions = {"title": 3}
    conflicts = detect_conflicts({"title": 1}, stored_versions, changed=("title",))
    assert conflicts == ("title",)


def test_a_writer_that_claims_no_version_never_conflicts() -> None:
    """How an import or an automation writes: it is not claiming to know the
    current state."""
    assert detect_conflicts(None, {"title": 9}, changed=("title",)) == ()


# --- validation -----------------------------------------------------------


def test_a_required_field_is_enforced_on_create() -> None:
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id=None, submitted_values={"amount": 1},
                      stored=None, decision=FULL, now=NOW)
    assert exc.value.outcome is not None
    assert any(e.code == "required" for e in exc.value.outcome.errors)


def test_a_range_rule_is_enforced() -> None:
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id=None,
                      submitted_values={"title": "x", "amount": 5_000_000},
                      stored=None, decision=FULL, now=NOW)
    assert any(e.code == "max" for e in exc.value.outcome.errors)  # type: ignore[union-attr]


def test_an_unknown_select_option_is_rejected() -> None:
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id=None,
                      submitted_values={"title": "x", "risk_type": "invented"},
                      stored=None, decision=FULL, now=NOW)
    assert any(e.code == "options" for e in exc.value.outcome.errors)  # type: ignore[union-attr]


def test_set_once_blocks_a_second_write_but_allows_the_first() -> None:
    _, created = prepare_write(COMPILED, CTX, row_id=None,
                               submitted_values={"title": "x", "reference": "PO-1"},
                               stored=None, decision=FULL, now=NOW)
    assert created.values["reference"] == "PO-1"

    stored = _stored(reference="PO-1")
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id="r1", submitted_values={"reference": "PO-2"},
                      stored=stored, decision=FULL, now=NOW)
    assert any(e.code == "set_once" for e in exc.value.outcome.errors)  # type: ignore[union-attr]


def test_a_write_without_the_action_is_refused_before_validation() -> None:
    read_only = Decision(allowed=frozenset({Action.READ}), readable_fields=ALL_FIELDS)
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id="r1", submitted_values={"title": "x"},
                      stored=_stored(), decision=read_only, now=NOW)
    assert exc.value.code == "forbidden"


# --- one transaction: row, audit, outbox ---------------------------------


def test_a_write_produces_exactly_one_audit_entry_and_one_outbox_envelope() -> None:
    pending, result = prepare_write(COMPILED, CTX, row_id="r1",
                                    submitted_values={"title": "Updated"},
                                    stored=_stored(), decision=FULL, now=NOW)
    assert pending.audit.audit_class is AuditClass.CHANGE
    assert pending.audit.channel == "grid"
    assert pending.audit.correlation_id == "c1"
    assert len(pending.envelope.events) == 1
    assert result.events[0].event_type is EventType.ROW_UPDATED


def test_the_commit_budget_is_enforced_rather_than_discovered() -> None:
    """children + parent + 1 audit + 1 outbox <= 500."""
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id="r1", submitted_values={"title": "x"},
                      stored=_stored(), decision=FULL, child_count=600, now=NOW)
    assert exc.value.code == "commit_too_large"


def test_an_event_never_carries_row_values() -> None:
    """AU-8 verbatim. A payload carrying values would make the event stream a
    second, unevaluated read path — trimmed for whoever wrote the row rather
    than for whoever consumes the event."""
    _, result = prepare_write(COMPILED, CTX, row_id="r1",
                              submitted_values={"title": "Updated"},
                              stored=_stored(), decision=FULL, now=NOW)
    payload = result.events[0].to_payload()
    assert "values" not in payload
    assert payload["changedFields"] == ["title"]
    assert_no_row_bodies(build_envelope(list(result.events)))


def test_the_row_carries_its_index_projection() -> None:
    """Written by the writer, so a row cannot exist without the generic index
    columns its Blueprint's views depend on."""
    pending, _ = prepare_write(COMPILED, CTX, row_id=None,
                               submitted_values={"title": "Alpha", "risk_type": "fraud", "amount": 100},
                               stored=None, decision=FULL, now=NOW)
    assert "fld_risk_type=fraud" in pending.document["eq"]
    assert pending.document["num0"] == 100


def test_a_no_op_update_is_refused_rather_than_writing_an_empty_delta() -> None:
    """An audit trail of writes that changed nothing is noise that makes the
    real entries harder to find."""
    with pytest.raises(WriteRejected) as exc:
        prepare_write(COMPILED, CTX, row_id="r1", submitted_values={"title": "Late filing"},
                      stored=_stored(), decision=FULL, now=NOW)
    assert exc.value.code == "noop"


def test_row_ids_are_opaque_and_unique() -> None:
    """Sequential ids leak volume and creation order; a timestamp id collides."""
    ids = {
        prepare_write(COMPILED, CTX, row_id=None, submitted_values={"title": "x"},
                      stored=None, decision=FULL, now=NOW)[1].row_id
        for _ in range(50)
    }
    assert len(ids) == 50
    assert all(len(i) == 32 and i.isalnum() for i in ids)


# --- audit trimming -------------------------------------------------------


def test_a_restricted_fields_delta_renders_as_withheld() -> None:
    """Without this the activity drawer hands out exactly the values PM-10 says
    a read of should be audited."""
    deltas = diff({"title": "old", "owner_rationale": "sealed"},
                  {"title": "new", "owner_rationale": "unsealed"})
    trimmed = trim_deltas(deltas, LIMITED)

    by_field = {d.field_id: d for d in trimmed}
    assert by_field["title"].before == "old"
    assert by_field["owner_rationale"].before == WITHHELD
    assert by_field["owner_rationale"].after == WITHHELD
