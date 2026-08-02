"""Authentication dependencies.

Rejection is centralised here rather than in middleware so that unauthenticated
endpoints exist by *not* declaring this dependency, instead of by appearing on
an exemption list inside the auth middleware. One list of public paths, in one
place, is easier to audit than two that can disagree.

This module deliberately answers only "who are you". Everything about "what may
you do" belongs to the permission library — which is why nothing here is named
``can_*``, ``has_permission`` or ``is_allowed``: the fitness suite bans those
identifiers outside ``lib/permissions`` precisely so that a second decision site
cannot grow here by accident.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from api.core.exceptions import AuthenticationError
from api.core.identity import AuthContext


def require_auth(request: Request) -> AuthContext:
    """Return the authenticated identity, or 401.

    Applied at router-include time rather than per route: Frame's endpoints are
    generated from Blueprint metadata, and a generator that forgot the
    dependency on one route would emit a silently unauthenticated endpoint.
    Defaulting to guarded and opting out explicitly is the safe direction.
    """
    auth = getattr(request.state, "auth", None)
    if auth is None:
        raise AuthenticationError()
    return auth  # type: ignore[no-any-return]


def optional_auth(request: Request) -> AuthContext | None:
    """For surfaces that render differently when signed in but do not require it."""
    return getattr(request.state, "auth", None)


CurrentUser = Annotated[AuthContext, Depends(require_auth)]
MaybeUser = Annotated[AuthContext | None, Depends(optional_auth)]
