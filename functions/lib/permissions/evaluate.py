"""The evaluator. The only place in Frame an allow/deny decision is made.

Pure: no I/O, no web framework, no store client. That is what lets the data
service, the query engine, the export pipeline, the audit-read path, the search
indexer and later the document generator and MCP surface all link the same
code — and it is enforced by a fitness test, because "we all call the same
library" decays into "we mostly call the same library" within a quarter.

Precedence, evaluated per (principal, action, row, field):

1. compile every rule whose principal matches, directly or through a group or
   role;
2. an explicit **deny at any scope beats every allow**, and the most specific
   matching deny is the one recorded and explained;
3. otherwise allows union — field-set allows union to a field set, row-condition
   allows union to a row predicate;
4. absence of any matching allow is denial, citing no rule;
5. the parent ceiling (PM-3) applies last and unconditionally;
6. **there is no evaluation input outside the compiled rule set.** No per-row
   grants, which is what makes compile-once sound and access review complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lib.grammar.ast import Expr, parse
from lib.grammar.evaluate import Context, Subject, matches
from lib.permissions.model import Action, Decision, Principal

if TYPE_CHECKING:
    from lib.blueprint.compile import CompiledBlueprint


@dataclass(frozen=True, slots=True)
class CompiledRule:
    index: int
    principals: frozenset[str]
    actions: frozenset[Action]
    effect: str                      # "allow" | "deny"
    condition: Expr | None
    field_ids: frozenset[str] | None
    max_band: int | None
    strict_attributes: bool

    @property
    def name(self) -> str:
        return f"rule[{self.index}]"

    @property
    def specificity(self) -> int:
        """How narrowly a rule is drawn.

        Used only to choose which deny to *report*. A field-scoped, condition-
        bearing deny explains a refusal far better than a blanket one, and the
        explanation is the whole point of surfacing a rule name at all.
        """
        score = 0
        if self.condition is not None:
            score += 2
        if self.field_ids is not None:
            score += 1
        if "*" not in self.principals:
            score += 1
        return score


@dataclass(frozen=True, slots=True)
class CompiledRuleSet:
    """Compiled once per Blueprint version and cached.

    The compile step exists so that rule parsing, principal normalisation and
    expression validation happen once rather than per row — which is what makes
    the sub-5ms per-row batch-amortised budget reachable.
    """

    blueprint_id: str
    version: int
    rules: tuple[CompiledRule, ...]
    all_field_ids: frozenset[str]
    restricted_field_ids: frozenset[str]

    def for_principal(self, principal: Principal) -> tuple[CompiledRule, ...]:
        identities = principal.identifiers()
        return tuple(r for r in self.rules if r.principals & identities)


def compile_rules(compiled: CompiledBlueprint) -> CompiledRuleSet:
    rules: list[CompiledRule] = []
    for i, rule in enumerate(compiled.blueprint.permissions):
        actions = frozenset(Action(a) for a in rule.actions if a in Action.__members__.values())
        rules.append(
            CompiledRule(
                index=i,
                principals=frozenset(rule.principals),
                actions=actions,
                effect=rule.effect,
                condition=parse(rule.row_condition) if rule.row_condition else None,
                field_ids=frozenset(rule.field_ids) if rule.field_ids else None,
                max_band=rule.max_band,
                strict_attributes=rule.strict_attributes,
            )
        )

    return CompiledRuleSet(
        blueprint_id=compiled.id,
        version=compiled.version,
        rules=tuple(rules),
        all_field_ids=frozenset(compiled.fields),
        restricted_field_ids=compiled.restricted_field_ids(),
    )


def evaluate_row(
    rule_set: CompiledRuleSet,
    principal: Principal,
    row: dict[str, Any],
    *,
    compiled: CompiledBlueprint,
    parent_decision: Decision | None = None,
    parent_row: dict[str, Any] | None = None,
) -> Decision:
    """The complete answer for one principal against one row.

    ``parent_decision`` is PM-3's ceiling. It is applied last and
    unconditionally: nobody reaches a child of a parent they cannot see, so a
    child row can never disclose the existence of its parent.
    """
    candidates = rule_set.for_principal(principal)
    if not candidates:
        return Decision()  # absence of a rule is denial, citing nothing

    # Conditions read the row's VALUES, not its envelope. Passing the whole
    # document would make every field reference miss — and a row condition that
    # silently never matches means a deny that never fires, which fails OPEN.
    # Accepting either shape keeps callers that already hold bare values working.
    ctx = Context(
        row=row.get("values", row) if "values" in row else row,
        parent=(parent_row.get("values", parent_row) if parent_row and "values" in parent_row else parent_row),
        subject=Subject(
            email=principal.email,
            subject=principal.subject,
            groups=principal.groups,
        ),
        allow_lists=principal.allow_lists,
        scope=_subject_scope(),
    )

    allowed: set[Action] = set()
    readable: set[str] = set()
    writable: set[str] = set()
    denied_actions: set[Action] = set()
    denied_fields: set[str] = set()
    best_deny: CompiledRule | None = None

    for rule in candidates:
        if rule.condition is not None and not _condition_holds(rule, ctx):
            continue

        scoped_fields = _fields_for(rule, rule_set, compiled)

        if rule.effect == "deny":
            denied_actions |= rule.actions
            if rule.field_ids is not None or rule.max_band is not None:
                denied_fields |= scoped_fields
            else:
                denied_fields |= rule_set.all_field_ids
            if best_deny is None or rule.specificity > best_deny.specificity:
                best_deny = rule
            continue

        allowed |= rule.actions
        if Action.READ in rule.actions:
            readable |= scoped_fields

        # CREATE and IMPORT contribute to the writable set as well as UPDATE.
        #
        # A grant to create rows IS a grant to write the fields it is scoped to,
        # and reading writability from UPDATE alone leaves a create-only grant
        # with an empty writable set. The visible consequence was that field
        # scoping had to be skipped entirely on create to make creation work at
        # all — which meant a principal who could not write a restricted field on
        # an existing row could populate it on a new one.
        if rule.actions & {Action.UPDATE, Action.CREATE, Action.IMPORT}:
            writable |= scoped_fields

    # A deny at any scope beats every allow.
    allowed -= denied_actions
    readable -= denied_fields
    writable -= denied_fields

    # The parent ceiling, last and unconditional.
    if parent_decision is not None:
        allowed &= parent_decision.allowed
        if not parent_decision.visible:
            allowed = set()

    restricted = (rule_set.all_field_ids - readable) if Action.READ in allowed else frozenset()

    return Decision(
        allowed=frozenset(allowed),
        readable_fields=frozenset(readable),
        writable_fields=frozenset(writable),
        restricted_fields=frozenset(restricted),
        masked=False,
        deciding_rule=best_deny.name if best_deny and not allowed else None,
    )


def may_at_blueprint_level(
    rule_set: CompiledRuleSet, principal: Principal, action: Action
) -> bool:
    """Could this principal EVER perform this action on this register?

    A cheap gate in front of per-row evaluation, never a replacement for it. It
    exists because the obvious implementation — evaluate against an empty row —
    is wrong in a way that is easy to ship: a grant conditioned on a field value
    does not match a row with no values, so the gate refuses a principal who can
    in fact see plenty of rows. That failure looks like a permission bug to the
    user and like correct behaviour to whoever wrote the gate.

    So: an explicit deny of the action closes the door, and otherwise any allow
    carrying the verb opens it. Every row is still evaluated individually.
    """
    candidates = rule_set.for_principal(principal)
    if any(r.effect == "deny" and action in r.actions and r.condition is None for r in candidates):
        return False
    return any(r.effect == "allow" and action in r.actions for r in candidates)


def writable_at_blueprint_level(
    rule_set: CompiledRuleSet,
    principal: Principal,
    compiled: Any = None,
) -> frozenset[str]:
    """Fields this principal could EVER write on this register.

    The same "could ever" shape as `may_at_blueprint_level`, and for the same
    reason: a grant conditioned on a field value does not match an empty row, so
    evaluating one would report an empty writable set for a principal who can in
    fact write plenty of rows.

    It exists so a create form can omit fields nobody will ever be allowed to
    fill. That is rendering a decision the server made, not making one — the
    write path still evaluates every field on every write, and a client that
    ignored this and sent the field anyway would be refused exactly as before.
    Nothing here is a gate; it is a label.

    Denies are honoured, unconditional ones only. A conditional deny may or may
    not apply to the row being created, and treating "sometimes denied" as
    "never writable" would hide a field the user can legitimately fill.
    """
    candidates = rule_set.for_principal(principal)

    writable: set[str] = set()
    denied: set[str] = set()

    for rule in candidates:
        scoped = _fields_for(rule, rule_set, compiled)
        if rule.effect == "deny":
            if rule.condition is not None:
                continue
            if rule.field_ids is not None or rule.max_band is not None:
                denied |= scoped
            else:
                denied |= rule_set.all_field_ids
        elif rule.actions & {Action.UPDATE, Action.CREATE, Action.IMPORT}:
            writable |= scoped

    return frozenset(writable - denied)


def _subject_scope() -> Any:
    from lib.grammar.ast import Scope

    # Permission rules are the one slot that reads the acting principal.
    return Scope.ROW_PARENT_SUBJECT


def _condition_holds(rule: CompiledRule, ctx: Context) -> bool:
    """Evaluate a row condition, resolving PM-2a allow-lists.

    ``strict_attributes`` decides what an unpopulated attribute means. The
    default — absence does not match, so an allow does not apply and a deny does
    not fire — is deliberate: Frappe's equivalent defaults the other way, which
    makes a row with a blank restricted field visible to everyone.
    """
    assert rule.condition is not None
    return matches(rule.condition, ctx, unknown_matches=rule.strict_attributes)


def _fields_for(
    rule: CompiledRule, rule_set: CompiledRuleSet, compiled: CompiledBlueprint
) -> set[str]:
    """Which fields a rule reaches.

    Bands come first because they are a set-membership test rather than a
    per-field rule evaluation, which is what makes the latency budget reachable
    on a wide Blueprint.
    """
    if rule.max_band is not None:
        return {
            fid
            for fid, cf in compiled.fields.items()
            if cf.definition.sensitivity <= rule.max_band
        }
    if rule.field_ids is not None:
        return set(rule.field_ids)
    return set(rule_set.all_field_ids)
