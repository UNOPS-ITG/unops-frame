"""The golden decision corpus.

Every case runs against **every registered consumer**, and a test fails if a
consumer exists that is not registered. One consumer proves nothing: a library
used in exactly one place is indistinguishable from logic that happens to live
in a separate file.

The headline case is the vision's own: a Project visible to the whole team,
whose child Risks are further gated so that conduct-typed rows are visible only
to the risk officer — with the risk officer resolved from a field on the parent
row, because that is what PM-1 actually specifies. It is inexpressible in stock
Frappe, which clears every child type's permission rows and delegates access
wholly to the parent.
"""

from __future__ import annotations

from typing import Any

import pytest

from lib.blueprint.compile import compile_blueprint
from lib.blueprint.model import (
    Blueprint,
    FieldDef,
    PermissionRule,
    SelectOption,
    Tier,
    ViewDefaults,
)
from lib.permissions import (
    Action,
    Decision,
    Principal,
    annotate_aggregate,
    compile_rules,
    evaluate_row,
    registered_consumers,
    trim_page,
    trim_row,
)

# --- the register ---------------------------------------------------------

EQ = lambda field, value: {  # noqa: E731 - a fixture helper, not production code
    "type": "binary",
    "op": "eq",
    "left": {"type": "field", "id": field},
    "right": {"type": "literal", "value": value},
}

RISK_BP = Blueprint.model_validate(
    {
        "id": "risk",
        "name": "Risks",
        "workspace_id": "ws1",
        "tier": Tier.TEAM,
        "fields": [
            FieldDef(id="title", label="Title", type="text", variant="single", indexed=True),
            FieldDef(
                id="risk_type", label="Risk type", type="single_select", indexed=True,
                options=[SelectOption(key="conduct", label="Conduct"), SelectOption(key="fraud", label="Fraud")],
            ),
            FieldDef(id="amount", label="Amount", type="number", variant="decimal", indexed=True),
            FieldDef(id="owner_rationale", label="Owner rationale", type="text", variant="long", sensitivity=2),
        ],
        "view_defaults": ViewDefaults(title_field="title"),
        "permissions": [
            # 0: the team sees everything except the restricted band.
            PermissionRule(principals=["group:project-team"], actions=["read"], max_band=1),
            # 1: risk officers see everything including band 2.
            PermissionRule(principals=["group:risk-officers"], actions=["read", "update", "export"]),
            # 2: conduct rows are withheld from the team. A deny beats every allow.
            PermissionRule(
                principals=["group:project-team"],
                actions=["read"],
                effect="deny",
                row_condition=EQ("risk_type", "conduct"),
            ),
        ],
    }
)
RISK = compile_blueprint(RISK_BP)
RULES = compile_rules(RISK)

TEAM = Principal(subject="maya", email="maya@unops.org", groups=frozenset({"project-team"}))
OFFICER = Principal(subject="ingrid", email="ingrid@unops.org", groups=frozenset({"risk-officers"}))
STRANGER = Principal(subject="nobody", email="nobody@unops.org")

ROWS: list[dict[str, Any]] = [
    {"id": "r1", "values": {"title": "Late filing", "risk_type": "fraud", "amount": 20_000, "owner_rationale": "escalated"}},
    {"id": "r2", "values": {"title": "Conduct case", "risk_type": "conduct", "amount": 50_000, "owner_rationale": "sealed"}},
    {"id": "r3", "values": {"title": "Supplier delay", "risk_type": "fraud", "amount": 30_000, "owner_rationale": "monitoring"}},
]


def _decide(principal: Principal, row: dict[str, Any], **kw: Any) -> Decision:
    return evaluate_row(RULES, principal, row, compiled=RISK, **kw)


# --- every consumer reaches the same decision ----------------------------


@pytest.mark.parametrize("consumer", registered_consumers(), ids=lambda c: c.key)
@pytest.mark.parametrize("principal", [TEAM, OFFICER, STRANGER], ids=lambda p: p.subject)
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_every_consumer_reaches_the_same_decision(consumer: Any, principal: Principal, row: dict[str, Any]) -> None:
    """The claim PM-4 makes, asserted rather than asserted-about.

    Four consumers x three principals x three rows. If any surface drifts, the
    divergence shows up here rather than in an audit finding.
    """
    expected = _decide(principal, row)
    actual = consumer.evaluate(RULES, principal, row, compiled=RISK)
    assert actual == expected, f"{consumer.key} disagrees with the evaluator"


def test_adding_a_consumer_without_registering_it_fails() -> None:
    """The registry is what stops "we all call the same library" decaying into
    "we mostly call the same library"."""
    keys = {c.key for c in registered_consumers()}
    assert keys == {"library", "row_stream", "export", "audit_read"}, (
        "A consumer was added or removed. Register it in lib/permissions/__init__.py "
        "and extend this assertion, so the corpus covers it."
    )


# --- the canonical case ---------------------------------------------------


def test_a_conduct_row_is_withheld_from_the_team_and_visible_to_the_officer() -> None:
    conduct = ROWS[1]
    assert _decide(TEAM, conduct).visible is False
    assert _decide(OFFICER, conduct).visible is True


def test_a_deny_beats_every_allow_and_names_itself() -> None:
    """The most specific matching deny is reported, because a field-scoped,
    condition-bearing rule explains a refusal far better than a blanket one."""
    decision = _decide(TEAM, ROWS[1])
    assert decision.allowed == frozenset()
    assert decision.deciding_rule == "rule[2]"


def test_absence_of_a_rule_is_denial_citing_nothing() -> None:
    decision = _decide(STRANGER, ROWS[0])
    assert decision.visible is False
    assert decision.deciding_rule is None


def test_a_band_scoped_grant_withholds_the_restricted_field_not_the_row() -> None:
    decision = _decide(TEAM, ROWS[0])
    assert decision.visible is True
    assert "owner_rationale" in decision.restricted_fields
    assert "amount" in decision.readable_fields


def test_export_is_a_distinct_action_from_read() -> None:
    """PM-8: a principal who may read may still not take the data out."""
    assert _decide(TEAM, ROWS[0]).may(Action.EXPORT) is False
    assert _decide(OFFICER, ROWS[0]).may(Action.EXPORT) is True


# --- trimming and annotation ---------------------------------------------


def test_a_withheld_field_is_a_typed_stub_never_an_absent_key() -> None:
    """Never omitted and never a type default: a zero where a number was
    withheld is a lie that then gets summed."""
    trimmed = trim_row(ROWS[0], _decide(TEAM, ROWS[0]))
    assert trimmed is not None
    assert trimmed["values"]["owner_rationale"] == {"restricted": True}
    assert trimmed["values"]["amount"] == 20_000
    assert "owner_rationale" in trimmed["values"]


def test_a_withheld_row_is_absent_from_the_array_and_counted() -> None:
    decisions = [_decide(TEAM, r) for r in ROWS]
    visible, annotation, columns = trim_page(ROWS, decisions)

    assert [r["id"] for r in visible] == ["r1", "r3"]
    assert annotation.visible == 2
    assert annotation.withheld == 1
    assert annotation.total == 3
    # Withheld on every visible row, so it renders as a column stub (GR-6).
    assert columns == frozenset({"owner_rationale"})


def test_the_annotation_is_an_object_not_a_sentence() -> None:
    """It has to render in six locales; a server-built English string cannot."""
    _, annotation, _ = trim_page(ROWS, [_decide(TEAM, r) for r in ROWS])
    assert annotation.certainty == "exact"
    assert isinstance(annotation.visible, int)
    assert isinstance(annotation.withheld, int)


def test_the_officer_sees_every_row_and_no_column_stub() -> None:
    decisions = [_decide(OFFICER, r) for r in ROWS]
    visible, annotation, columns = trim_page(ROWS, decisions)
    assert annotation.withheld == 0
    assert columns == frozenset()
    assert visible[1]["values"]["owner_rationale"] == "sealed"


def test_an_aggregate_computes_over_the_full_set_and_says_so() -> None:
    """The honest answer to a real dilemma: computing over the trimmed set
    misleads about the total, computing silently over the full set leaks that
    hidden rows exist."""
    decisions = [_decide(TEAM, r) for r in ROWS]
    withheld = sum(1 for d in decisions if not d.visible)
    result = annotate_aggregate([r["values"]["amount"] for r in ROWS], withheld)

    assert result["value"] == 100_000  # all three, not just the visible two
    assert result["annotation"] == {"computedOver": "full", "withheldRows": 1}


# --- PM-3 composition -----------------------------------------------------


def test_a_child_is_invisible_when_its_parent_is() -> None:
    """The parent ceiling applies last and unconditionally, so a child row can
    never disclose the existence of a parent the reader cannot see."""
    parent_denied = Decision()  # cannot read the parent
    decision = _decide(OFFICER, ROWS[0], parent_decision=parent_denied)
    assert decision.visible is False


def test_a_child_narrows_within_the_parent_ceiling_never_beyond_it() -> None:
    parent_read_only = Decision(allowed=frozenset({Action.READ}))
    decision = _decide(OFFICER, ROWS[0], parent_decision=parent_read_only)
    assert decision.may(Action.READ) is True
    # The officer's own rule grants update; the parent's ceiling does not.
    assert decision.may(Action.UPDATE) is False


def test_a_rule_can_read_a_denormalised_parent_attribute() -> None:
    """PM-1's instance-context binding: "visible to the parent's risk officer",
    which is what makes the canonical example expressible at all."""
    bp = RISK_BP.model_copy(deep=True)
    bp.permissions = [
        PermissionRule(
            principals=["*"],
            actions=["read"],
            row_condition={
                "type": "binary",
                "op": "eq",
                "left": {"type": "parent_field", "id": "risk_officer"},
                "right": {"type": "subject", "attribute": "email"},
            },
        )
    ]
    rules = compile_rules(compile_blueprint(bp))
    parent = {"risk_officer": "ingrid@unops.org"}

    allowed = evaluate_row(rules, OFFICER, ROWS[0], compiled=RISK, parent_row=parent)
    refused = evaluate_row(rules, TEAM, ROWS[0], compiled=RISK, parent_row=parent)
    assert allowed.visible is True
    assert refused.visible is False


# --- PM-2a allow-lists ----------------------------------------------------


def test_a_principal_allow_list_scopes_without_an_expression_per_person() -> None:
    """The stored-record form, which is what makes it always push-downable and
    therefore affordable at grid scale."""
    bp = RISK_BP.model_copy(deep=True)
    bp.permissions = [
        PermissionRule(
            principals=["*"],
            actions=["read"],
            row_condition={
                "type": "in",
                "value": {"type": "field", "id": "risk_type"},
                "options": [{"type": "allow_list", "field": "risk_type"}],
            },
        )
    ]
    rules = compile_rules(compile_blueprint(bp))

    scoped = Principal(subject="scoped", allow_lists={"risk_type": frozenset({"fraud"})})
    assert evaluate_row(rules, scoped, ROWS[0], compiled=RISK).visible is True   # fraud
    assert evaluate_row(rules, scoped, ROWS[1], compiled=RISK).visible is False  # conduct


# --- attribute absence ----------------------------------------------------


def test_an_allow_does_not_apply_to_a_row_with_an_unpopulated_attribute() -> None:
    """Frappe's equivalent defaults the other way, so a blank restricted field
    makes the row visible to everyone. BP-15 makes half-populated rows the norm
    at exactly the moment promotion attaches rules to them."""
    bp = RISK_BP.model_copy(deep=True)
    bp.permissions = [
        PermissionRule(principals=["*"], actions=["read"], row_condition=EQ("risk_type", "fraud"))
    ]
    rules = compile_rules(compile_blueprint(bp))
    blank = {"id": "r9", "values": {"title": "No type set"}}
    assert evaluate_row(rules, TEAM, blank, compiled=RISK).visible is False


def test_strict_attributes_makes_a_deny_fire_on_an_absent_value() -> None:
    bp = RISK_BP.model_copy(deep=True)
    bp.permissions = [
        PermissionRule(principals=["*"], actions=["read"]),
        PermissionRule(
            principals=["*"], actions=["read"], effect="deny",
            row_condition=EQ("risk_type", "conduct"), strict_attributes=True,
        ),
    ]
    rules = compile_rules(compile_blueprint(bp))
    blank = {"id": "r9", "values": {"title": "No type set"}}
    assert evaluate_row(rules, TEAM, blank, compiled=RISK).visible is False


# --- the reserved masking flag -------------------------------------------


def test_a_row_condition_reads_values_not_the_envelope() -> None:
    """Regression, and the failure mode is the dangerous direction.

    A row document is ``{"id": …, "values": {…}}``. Evaluating a condition
    against the envelope makes every field reference miss, so the condition
    never matches — which means a DENY never fires and the rule fails OPEN. It
    looks like working code and quietly grants access.

    Both shapes are accepted, and both must reach the same decision.
    """
    enveloped = {"id": "r2", "values": {"title": "Conduct case", "risk_type": "conduct"}}
    bare = {"title": "Conduct case", "risk_type": "conduct"}

    assert _decide(TEAM, enveloped).visible is False
    assert _decide(TEAM, bare).visible is False
    assert _decide(OFFICER, enveloped).visible is True


def test_masked_is_present_and_always_false() -> None:
    """Reserving the field costs nothing; adding it later would change the
    signature every consumer depends on."""
    assert _decide(OFFICER, ROWS[0]).masked is False
