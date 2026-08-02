"""Turning an authenticated identity into a Principal the evaluator can use.

Deliberately a separate step from authentication. ``AuthContext`` says who the
request is; a ``Principal`` additionally carries group memberships, workspace and
Blueprint roles and PM-2a allow-lists — all of which need I/O. Keeping them apart
is what lets the auth middleware stay pure and the permission library stay the
only thing that knows what access means.

**Keyed on the stable subject, never the email.** An address is mutable and
reassignable, so keying grants on one means a renamed or recycled address
silently inherits or loses them, and PM-11 access review stops being sound.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lib.permissions.model import Principal

if TYPE_CHECKING:
    from api.core.identity import AuthContext

MEMBERSHIPS = "members"
ALLOW_LISTS = "allowLists"


def resolve_principal(db: Any, workspace_id: str, auth: AuthContext) -> Principal:
    """Read this identity's memberships and allow-lists for one workspace.

    Membership is per workspace, so the same person is a different Principal in
    two workspaces — which is the point. A cached "global" Principal would carry
    one workspace's roles into another.
    """
    from lib.paths import workspace

    member = (
        workspace(db, workspace_id).collection(MEMBERSHIPS).document(auth.subject).get()
    )
    data: dict[str, Any] = (member.to_dict() or {}) if member.exists else {}

    return Principal(
        subject=auth.subject,
        email=auth.email,
        groups=frozenset(data.get("groups", ())),
        workspace_roles=frozenset(data.get("roles", ())),
        blueprint_roles=frozenset(data.get("blueprintRoles", ())),
        is_service=auth.channel == "service",
        allow_lists=_read_allow_lists(data),
    )


def _read_allow_lists(data: dict[str, Any]) -> dict[str, frozenset[str]]:
    """PM-2a scopes, materialised per principal.

    Stored as a resolved value list rather than as a condition, which is exactly
    what makes this shape *always* push-downable — and therefore affordable at
    grid scale where a general attribute expression is not.

    A list past its staleness bound **freezes**; it is never widened and never
    silently dropped. Dropping it would open the register to a principal whose
    scope could not be refreshed, which is the failure direction that matters.
    """
    raw = data.get(ALLOW_LISTS) or {}
    return {
        field_id: frozenset(values)
        for field_id, values in raw.items()
        if isinstance(values, (list, tuple, set))
    }
