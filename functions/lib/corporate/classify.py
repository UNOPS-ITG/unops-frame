"""Disclosure classification: which relations Frame may cache, and which it
must resolve live in the user's own context.

**Assigned by mechanical probe, never by assertion.** Nobody ticks a box saying
a dimension is public. Four independent checks run, and **any one of them
failing forces `entitled`** — including "the question could not be answered",
because an unanswered audience question is not a negative answer.

The governing line, from which everything else follows:

    Frame caches no label that anyone may be denied.

That is the difference between a projection and a permission bypass.

Why the fast path is worth having at all: there is no warehouse-side trick that
makes an entitlement-varying picker fast. Query results are *not cached* for
tables under row-level security; BI Engine does not accelerate them; a
materialized view over such a table performs like the base table. Speed has to
come from Frame — so for data BigQuery has already ruled everyone may see,
executing per-user is theatre that costs latency and money to reach a known
conclusion. User-context execution is preserved exactly where it is
load-bearing.

The four checks:

1. **Dataset IAM** must show the all-staff group holding a read role. The most
   common narrowing at UNOPS leaves no trace in a row-set comparison, so a
   comparison alone cannot see it.
2. **No row access policies, and no policy tag on any projected column** —
   including the key and the code. A project code encoding geography discloses
   as surely as a name does.
3. **A floor-principal comparison** against a principal that is a member of
   exactly the all-staff group and nothing else.
4. **No Frame surface broader than the dataset's audience.**

Policies attach to **base tables, not views**, so a registered view is resolved
to its base tables and those are probed. A view silently re-pointed at a
different base table is a drift event, not a re-classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field

from lib.corporate.model import Dimension, Disclosure, Fact

ALL_STAFF_ROLES = frozenset({"roles/bigquery.dataViewer", "roles/bigquery.dataEditor"})
"""Roles that actually confer a read. `bigquery.user` and `jobUser` do not —
they permit running a job, not reading a table, and treating them as read access
is how a dimension gets classified open on the strength of a grant that grants
nothing."""


@dataclass(slots=True)
class Probe:
    """What the four checks observed. Every field defaults to the UNSAFE answer.

    That is the whole design of this dataclass: a probe that failed to run, or a
    field a caller forgot to populate, produces `entitled`. The alternative —
    defaults that mean "fine" — turns a network timeout into a disclosure.
    """

    all_staff_can_read: bool = False
    """Check 1. False also when the IAM read failed."""

    row_access_policies: int = 0
    """Check 2a. Non-zero forces entitled; policies attach to base tables."""

    tagged_columns: tuple[str, ...] = ()
    """Check 2b. Any projected column carrying a non-Level-0 policy tag."""

    floor_principal_sees_all_rows: bool = False
    """Check 3. False also when the comparison could not be made."""

    frame_surface_is_wider: bool = False
    """Check 4. True when Frame would expose this to an audience broader than
    the dataset's own."""

    base_tables_resolved: bool = False
    """Whether the view was successfully resolved to its base tables. False
    means checks 1–3 were run against something that cannot carry a policy, so
    they proved nothing."""

    probe_errors: tuple[str, ...] = ()

    reasons: list[str] = dc_field(default_factory=list)


def classify(probe: Probe) -> tuple[Disclosure, list[str]]:
    """The four checks. Any failure forces `entitled`, and says why."""
    reasons: list[str] = []

    if not probe.base_tables_resolved:
        reasons.append(
            "the view could not be resolved to its base tables, so the policy checks "
            "ran against something that cannot carry a policy"
        )
    if probe.probe_errors:
        reasons.extend(f"probe error: {e}" for e in probe.probe_errors)
    if not probe.all_staff_can_read:
        reasons.append("the all-staff group does not hold a read role on the dataset")
    if probe.row_access_policies:
        reasons.append(f"{probe.row_access_policies} row access policy(ies) on the base tables")
    if probe.tagged_columns:
        reasons.append(
            "policy tags on projected columns: " + ", ".join(sorted(probe.tagged_columns))
        )
    if not probe.floor_principal_sees_all_rows:
        reasons.append("a floor principal did not see the full row set")
    if probe.frame_surface_is_wider:
        reasons.append("Frame would expose this more widely than the dataset's own audience")

    if reasons:
        return Disclosure.ENTITLED, reasons
    return Disclosure.OPEN, ["all four disclosure checks passed"]


def tagged_columns(relation: Dimension | Fact) -> tuple[str, ...]:
    """Every projected column carrying a tag above Level 0.

    Includes the business key. A project code that encodes geography discloses
    as surely as a name, and a classifier that exempted keys because "it is only
    an identifier" would be wrong in exactly the cases that matter.
    """
    if isinstance(relation, Dimension):
        return tuple(a.name for a in relation.attributes if not a.is_open)

    # A fact's tagged columns are usually NOT its measures — a recruitment
    # fact's sensitive columns are panel member names, and the one numeric
    # column on it is a harmless count. Reading measures alone classified such a
    # table as open.
    tagged = set(relation.restricted_columns)
    tagged |= {
        m.name
        for m in relation.measures
        if (m.policy_tag or "").strip() != "" and not (m.policy_tag or "").startswith("Level 0")
    }
    return tuple(sorted(tagged))


def classify_relation(
    relation: Dimension | Fact, probe: Probe
) -> tuple[Disclosure, list[str]]:
    """Classify one relation, folding its own column tags into the probe.

    The caller supplies the IAM and policy observations; the column tags come
    from the catalogue, so a relation whose columns are tagged cannot be
    classified open even by a probe that forgot to look.
    """
    tags = tagged_columns(relation)
    merged = Probe(
        all_staff_can_read=probe.all_staff_can_read,
        row_access_policies=probe.row_access_policies,
        tagged_columns=tuple(sorted(set(probe.tagged_columns) | set(tags))),
        floor_principal_sees_all_rows=probe.floor_principal_sees_all_rows,
        frame_surface_is_wider=probe.frame_surface_is_wider,
        base_tables_resolved=probe.base_tables_resolved,
        probe_errors=probe.probe_errors,
    )
    return classify(merged)


def label_visibility(dimension: Dimension, disclosure: Disclosure) -> Disclosure:
    """Whether a stored label snapshot may be rendered to anyone.

    A row stores `{key, label snapshot, snapshotAt, registryVersion}` so the grid
    can filter, sort, group, export and search without touching BigQuery. That
    snapshot is a cached label — and a cached label on an entitled dimension is a
    quiet bypass of the warehouse policy, which is why an entitled dimension's
    unresolvable key renders as a PM-5 restricted stub instead.
    """
    return Disclosure.OPEN if disclosure is Disclosure.OPEN else Disclosure.ENTITLED
