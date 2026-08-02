"""The disclosure probe: deciding, mechanically, what Frame may cache.

Four checks, any one of which failing forces `entitled` — including "the check
could not be run", because an unanswered audience question is not a negative
answer. `classify.py` holds that logic; this module gathers the evidence.

**Policies attach to base tables, not to views.** Every registered relation in
`unops-datahub` is a view over a base table, so the probe resolves each one and
inspects what it actually reads. That is not a theoretical concern here: the
base `Dimensions` dataset carries 85 policy-tagged columns and grants no
all-staff role, while the published `Dimensions_Api` layer carries no tags and
does grant one. A probe that looked only at the published layer would see an
untagged, all-staff-readable view of a table whose columns are protected.

**Three checks are implementable today and two are not, for different reasons,
and the difference matters.**

* Check 1 (dataset IAM) and check 2b (column policy tags) work now.
* Check 2a (row access policies) fails: `INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
  is not readable with the access Frame currently has. Recorded as an error, not
  a pass.
* Check 3 (floor-principal comparison) needs a principal that is a member of
  exactly the all-staff group and nothing else. It is not provisioned, so it is
  reported as unperformed.

Check 3 is the one that cannot be worked around, and the reason is concrete: a
privileged account cannot answer the question by reading. Reading a
policy-tagged column through the published view with a developer's credentials
succeeds — and it also succeeds directly against the base table, which means the
result says nothing about what an ordinary staff member would see. Only a
principal with exactly the floor's grants can distinguish "everyone may read
this" from "you may read this".

Until check 3 can run, **nothing is classified open**, which is the correct and
safe outcome rather than a limitation to route around.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from lib.corporate.classify import Probe
from lib.corporate.model import Dimension, Fact

logger = logging.getLogger(__name__)

ALL_STAFF_GROUP = "g.reporting.allpersonnel@unops.org"
"""The group every staff member belongs to.

Configurable per deployment, but named here because the check is meaningless
without knowing which group represents "everyone". A probe that guessed would
either classify everything entitled (harmless, useless) or match the wrong group
(not harmless).
"""

READ_ROLES = frozenset({"READER", "roles/bigquery.dataViewer", "roles/bigquery.dataEditor", "OWNER", "WRITER"})
"""Roles that actually confer a read on a dataset.

`bigquery.user` and `jobUser` do not — they permit running a job, not reading a
table. Treating them as read access is how a dimension gets classified open on
the strength of a grant that grants nothing.
"""

# `FROM unops-datahub.Dimensions.Absence t` — unquoted, three parts. Backticks
# are tolerated because a hand-edited view may use them.
_BASE_TABLE = re.compile(
    r"\bFROM\s+`?([a-z][a-z0-9\-]{4,28}[a-z0-9])`?\.`?(\w+)`?\.`?(\w+)`?",
    re.IGNORECASE,
)


class WarehouseInspector(Protocol):
    """What the probe needs to ask the warehouse.

    A protocol so the probe's *logic* — which is where a mistake is a
    disclosure — is testable without credentials.
    """

    def dataset_access(self, project: str, dataset: str) -> list[dict[str, Any]] | None:
        """Dataset IAM entries, or None if they could not be read."""
        ...

    def view_definition(self, project: str, dataset: str, table: str) -> str | None: ...

    def tagged_columns(self, project: str, dataset: str, table: str) -> tuple[str, ...] | None:
        """Columns carrying a real BigQuery policy tag, or None if unreadable."""
        ...

    def row_access_policy_count(self, project: str, dataset: str, table: str) -> int | None:
        """Row access policies on the table, or None if the view is unreadable."""
        ...


@dataclass(frozen=True, slots=True)
class BaseTable:
    project: str
    dataset: str
    table: str

    @property
    def id(self) -> str:
        return f"{self.project}.{self.dataset}.{self.table}"


def resolve_base_tables(definition: str | None) -> tuple[BaseTable, ...]:
    """The tables a view actually reads.

    Deliberately simple, and deliberately fails closed: a definition it cannot
    parse yields nothing, and the caller treats "no base tables resolved" as a
    failed check rather than as a view with no policies. The published views in
    this warehouse are one `SELECT … FROM project.dataset.table` each; anything
    more elaborate should stop the probe rather than be guessed at.
    """
    if not definition:
        return ()

    # Strip SQL line comments, so a table name inside the generator's `----`
    # banners cannot be mistaken for a real reference.
    #
    # The terminator is `[\r\n]`, not `\n`. The published views separate lines
    # with a bare CARRIAGE RETURN — no newline anywhere in the definition — so a
    # stripper anchored on `\n` consumes the entire statement including its FROM
    # clause. Nothing raises: the view resolves to no base tables, the probe
    # records a failed check, and every relation stays entitled for a reason
    # that points at the view rather than at the parser.
    cleaned = re.sub(r"--[^\r\n]*", " ", definition)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)

    seen: dict[str, BaseTable] = {}
    for project, dataset, table in _BASE_TABLE.findall(cleaned):
        base = BaseTable(project, dataset, table)
        seen.setdefault(base.id, base)
    return tuple(seen.values())


def all_staff_can_read(
    access: list[dict[str, Any]] | None, group: str = ALL_STAFF_GROUP
) -> bool:
    """Check 1. Does the all-staff group hold a role that confers a read?

    `None` — meaning the IAM could not be read — is False, not an exception. The
    probe's job is to gather evidence; the classifier decides, and it treats
    absence of evidence as failure.
    """
    if not access:
        return False

    target = group.strip().lower()
    for entry in access:
        who = (
            entry.get("groupByEmail")
            or entry.get("userByEmail")
            or entry.get("iamMember", "").removeprefix("group:")
            or ""
        )
        if str(who).strip().lower() != target:
            continue
        if str(entry.get("role", "")).strip() in READ_ROLES:
            return True
    return False


def probe_relation(
    relation: Dimension | Fact,
    inspector: WarehouseInspector,
    *,
    project: str,
    all_staff_group: str = ALL_STAFF_GROUP,
    frame_surface_is_wider: bool = False,
) -> Probe:
    """Gather the evidence for one relation.

    Every failure is recorded as an error rather than swallowed, so a relation
    that could not be probed is visibly unprobed rather than quietly entitled
    for an unstated reason.
    """
    errors: list[str] = []

    # Check 1 is asked of the dataset the VIEW lives in, because that is what
    # grants access to a reader. Checks 2a and 2b are asked of the base tables,
    # because that is where policies attach. Asking either question of the wrong
    # layer is the whole failure mode this split exists to avoid.
    access = inspector.dataset_access(project, relation.dataset)
    if access is None:
        errors.append(f"could not read IAM on dataset {relation.dataset}")

    definition = inspector.view_definition(project, relation.dataset, relation.table)
    bases = resolve_base_tables(definition)
    if not bases:
        errors.append(
            f"could not resolve {relation.id} to its base tables, so the policy "
            "checks would have run against a view, which cannot carry a policy"
        )

    tagged: set[str] = set()
    policies = 0
    for base in bases:
        columns = inspector.tagged_columns(base.project, base.dataset, base.table)
        if columns is None:
            errors.append(f"could not read column policy tags on {base.id}")
        else:
            tagged |= set(columns)

        count = inspector.row_access_policy_count(base.project, base.dataset, base.table)
        if count is None:
            errors.append(f"could not read row access policies on {base.id}")
        else:
            policies += count

    return Probe(
        all_staff_can_read=all_staff_can_read(access, all_staff_group),
        row_access_policies=policies,
        tagged_columns=tuple(sorted(tagged)),
        # Check 3. Not implemented, and not defaulted to True: a floor principal
        # is a provisioned identity Frame does not have, and asserting a check
        # that never ran is exactly what `classify` refuses to accept.
        floor_principal_sees_all_rows=False,
        frame_surface_is_wider=frame_surface_is_wider,
        base_tables_resolved=bool(bases),
        probe_errors=(
            *errors,
            "check 3 (floor-principal comparison) has not been performed: no floor "
            "principal is provisioned. A privileged account cannot answer this "
            "question — it can read the protected column both through the view and "
            "directly, so its success says nothing about what an ordinary staff "
            "member sees.",
        ),
    )


def probe_catalogue(
    relations: list[Dimension | Fact],
    inspector: WarehouseInspector,
    *,
    project: str,
    all_staff_group: str = ALL_STAFF_GROUP,
) -> dict[str, Probe]:
    """Probe every relation, caching per dataset and base table.

    The caching is not an optimisation detail: without it a 555-dimension sweep
    asks for the same dataset's IAM 555 times, and the probe becomes the
    expensive part of a job whose whole point is to be cheap enough to schedule.
    """
    return {
        relation.id: probe_relation(
            relation, inspector, project=project, all_staff_group=all_staff_group
        )
        for relation in relations
    }
