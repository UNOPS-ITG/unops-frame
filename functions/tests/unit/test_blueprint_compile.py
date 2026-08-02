"""The Blueprint validator and compiler.

BP-26 is the only Blueprint-time validator, and it matters more here than in a
hand-authored system because an AI drafts Blueprints (BP-16, BP-17). An
unguarded draft with a hidden required field is a Blueprint nobody can ever save
a row against, reported as a platform bug rather than a modelling mistake.
"""

from __future__ import annotations

import pytest

from lib.blueprint.compile import (
    CompilationError,
    build_row_projection,
    compile_blueprint,
)
from lib.blueprint.model import (
    Blueprint,
    ChildCollection,
    FieldDef,
    PermissionRule,
    SelectOption,
    Tier,
    ViewDefaults,
    WorkflowState,
    WorkflowTransition,
)
from lib.blueprint.registry import get_registry
from lib.blueprint.validate import validate_blueprint


def _bp(**overrides: object) -> Blueprint:
    base: dict[str, object] = {
        "id": "vendor_risk",
        "name": "Vendor Risk Register",
        "workspace_id": "ws1",
        "tier": Tier.TEAM,
        "fields": [
            FieldDef(id="vendor_name", label="Vendor", type="text", variant="single", indexed=True),
            FieldDef(
                id="risk_type",
                label="Risk type",
                type="single_select",
                indexed=True,
                options=[SelectOption(key="conduct", label="Conduct"), SelectOption(key="financial", label="Financial")],
            ),
            FieldDef(id="amount", label="Amount", type="number", variant="decimal", indexed=True),
            FieldDef(id="owner_rationale", label="Rationale", type="text", variant="long", sensitivity=2),
        ],
        "view_defaults": ViewDefaults(title_field="vendor_name"),
    }
    base.update(overrides)
    return Blueprint.model_validate(base)


# --- the happy path -------------------------------------------------------


def test_a_coherent_blueprint_validates_and_compiles() -> None:
    compiled = compile_blueprint(_bp())
    assert compiled.id == "vendor_risk"
    assert compiled.title_field == "vendor_name"
    assert set(compiled.fields) == {"vendor_name", "risk_type", "amount", "owner_rationale"}


def test_restricted_fields_are_precomputed_from_the_band_threshold() -> None:
    compiled = compile_blueprint(_bp())
    assert compiled.field("owner_rationale").is_restricted is True
    assert compiled.field("vendor_name").is_restricted is False
    assert compiled.restricted_field_ids() == frozenset({"owner_rationale"})


def test_restricted_fields_are_never_searchable() -> None:
    """An index is a copy of your data, and a careless one is a permission
    bypass with a query box (SR-6)."""
    bp = _bp()
    bp.fields[3].searchable = True  # owner_rationale, band 2
    bp.fields[0].searchable = True
    compiled = compile_blueprint(bp)
    assert "vendor_name" in compiled.searchable_fields
    assert "owner_rationale" not in compiled.searchable_fields


# --- the indexable projection --------------------------------------------


def test_sortable_fields_get_typed_generic_slots() -> None:
    """Index generic slots, not fields, so the index count is O(slots) rather
    than O(Blueprints x view shapes)."""
    plan = compile_blueprint(_bp()).index_plan
    assert plan.sort_slots["vendor_name"] == "txt0"
    assert plan.sort_slots["risk_type"] == "txt1"
    assert plan.sort_slots["amount"] == "num0"


def test_slot_pressure_is_reported_rather_than_silently_exhausted() -> None:
    """The slot budget is a product constraint users feel as "you cannot sort by
    this column server-side", so it has to be visible."""
    many = [
        FieldDef(id=f"n{i}", label=f"N{i}", type="number", variant="decimal", indexed=True)
        for i in range(10)
    ]
    bp = _bp(fields=[*_bp().fields, *many])
    plan = compile_blueprint(bp).index_plan

    assert plan.slot_pressure["num"] == "8/8"
    # 11 numeric fields declared indexed, 8 slots: 3 cannot be served.
    assert len(plan.unassignable) == 3
    assert all(f.startswith("n") for f in plan.unassignable)


def test_row_projection_emits_equality_tokens_and_slot_mirrors() -> None:
    compiled = compile_blueprint(_bp())
    projection = build_row_projection(
        compiled, {"vendor_name": "Acme", "risk_type": "conduct", "amount": 50000}
    )
    assert set(projection["eq"]) == {
        "fld_vendor_name=Acme",
        "fld_risk_type=conduct",
        "fld_amount=50000",
    }
    assert projection["txt0"] == "Acme"
    assert projection["num0"] == 50000


def test_projection_skips_absent_and_structured_values() -> None:
    compiled = compile_blueprint(_bp())
    projection = build_row_projection(compiled, {"vendor_name": None, "risk_type": {"restricted": True}})
    assert "eq" not in projection
    assert "txt0" not in projection


# --- rule-referenced fields ----------------------------------------------


def test_rule_referenced_fields_are_walked_out_of_the_ast() -> None:
    """Expressions are stored as AST, never strings, which is what makes this a
    reliable tree walk rather than a regex over user text — and it drives the
    child re-stamp fan-out, where being wrong is a silent permission leak."""
    bp = _bp(
        permissions=[
            PermissionRule(
                principals=["group:risk-officers"],
                actions=["read"],
                row_condition={
                    "type": "binary",
                    "op": "eq",
                    "left": {"type": "field", "id": "risk_type"},
                    "right": {"type": "literal", "value": "conduct"},
                },
                field_ids=["owner_rationale"],
            )
        ]
    )
    assert compile_blueprint(bp).rule_referenced_fields == frozenset({"risk_type", "owner_rationale"})


# --- BP-26: what the validator refuses ------------------------------------


def test_refuses_a_required_hidden_field_with_no_default() -> None:
    """The unsaveable Blueprint, and exactly what an unguarded AI draft produces."""
    bp = _bp()
    bp.fields.append(FieldDef(id="secret_code", label="Code", type="text", required=True, hidden=True))
    report = validate_blueprint(bp)
    assert not report.ok
    assert any(p.check == "unsaveable" for p in report.problems)
    with pytest.raises(CompilationError):
        compile_blueprint(bp)


def test_refuses_a_field_id_that_collides_with_system_metadata() -> None:
    bp = _bp()
    bp.fields.append(FieldDef(id="created_at", label="Created", type="date"))
    assert any(p.check == "field-id" for p in validate_blueprint(bp).problems)


def test_refuses_a_long_text_field_declared_indexed() -> None:
    bp = _bp()
    bp.fields[3].indexed = True  # owner_rationale is variant "long"
    assert any(p.check == "indexed" for p in validate_blueprint(bp).problems)


def test_refuses_a_type_that_is_declared_but_not_yet_available() -> None:
    """A more useful message than "unknown type": the type exists and is simply
    not available in this phase."""
    bp = _bp()
    bp.fields.append(FieldDef(id="doc", label="Doc", type="attachment"))
    problems = validate_blueprint(bp).problems
    assert any("not available until P2" in p.message for p in problems)


def test_requires_a_title_field_at_team_tier_and_above() -> None:
    """Reference chips, notification subjects, search results, generated
    filenames and audit entries all assume a row can be named."""
    bp = _bp(view_defaults=ViewDefaults())
    assert any(p.check == "view-defaults" for p in validate_blueprint(bp).problems)

    personal = _bp(tier=Tier.PERSONAL, view_defaults=ViewDefaults())
    assert validate_blueprint(personal).ok


def test_refuses_a_permission_verb_without_its_dependency() -> None:
    bp = _bp(permissions=[PermissionRule(principals=["user:a@unops.org"], actions=["publish"])])
    problems = validate_blueprint(bp).problems
    assert any("without 'read'" in p.message for p in problems)


def test_refuses_a_transition_that_revives_a_cancelled_record() -> None:
    bp = _bp(
        states=[
            WorkflowState(key="void", label="Void", lifecycle_status="cancelled"),
            WorkflowState(key="approved", label="Approved", lifecycle_status="submitted"),
        ],
        transitions=[WorkflowTransition(from_state="void", to_state="approved", label="Reinstate")],
    )
    assert any("revives a cancelled record" in p.message for p in validate_blueprint(bp).problems)


def test_refuses_both_submittable_and_freeze() -> None:
    """Submittable is for records corrected by amendment; freeze is for records
    corrected not at all. Both means no coherent answer to "this is wrong"."""
    bp = _bp(
        states=[WorkflowState(key="approved", label="Approved")],
        lifecycle={"submittable": True, "freeze_on_state": "approved"},
    )
    assert any("never both" in p.message for p in validate_blueprint(bp).problems)


def test_refuses_a_child_collection_over_the_transaction_budget() -> None:
    """children + parent + 1 audit + 1 outbox <= 500 per commit."""
    bp = _bp(children=[ChildCollection(id="findings", label="Findings", blueprint="finding", max_rows=400)])
    assert any("transactional save budget" in p.message for p in validate_blueprint(bp).problems)


def test_refuses_a_read_time_formula_that_is_indexed() -> None:
    bp = _bp()
    bp.fields.append(
        FieldDef(
            id="total", label="Total", type="formula", materialized=False, indexed=True,
            expression={"type": "field", "id": "amount"},
        )
    )
    assert any("read-time formula" in p.message for p in validate_blueprint(bp).problems)


def test_reports_every_problem_at_once_rather_than_the_first() -> None:
    """A steward should fix everything in one pass, not play whack-a-mole."""
    bp = _bp(view_defaults=ViewDefaults(title_field="nope"))
    bp.fields.append(FieldDef(id="Bad-ID", label="Bad", type="text"))
    bp.fields.append(FieldDef(id="hidden_req", label="H", type="text", required=True, hidden=True))
    report = validate_blueprint(bp)
    assert len({p.check for p in report.problems}) >= 3


def test_the_registry_declares_disabled_types_so_the_extension_path_is_real() -> None:
    reg = get_registry()
    assert "attachment" in reg.declared_keys()
    assert "attachment" not in reg.enabled_keys()
    assert reg.bands.is_at_or_above_restricted(2) is True
    assert reg.bands.is_at_or_above_restricted(1) is False
