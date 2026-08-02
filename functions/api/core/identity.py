"""Wire identity: who the request says it is, before any authorisation.

Deliberately NOT a Principal. A ``Principal`` — the thing the permission library
evaluates — additionally carries group memberships, workspace and Blueprint
roles and PM-2a allow-lists, all of which need I/O to resolve. Keeping them
apart means the authentication middleware stays pure and the permission library
stays the only thing that knows what access means.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AuthChannel = Literal["iap", "dev-bypass", "service"]


@dataclass(frozen=True, slots=True)
class AuthContext:
    """An authenticated identity, attached to ``scope["state"]["auth"]``."""

    subject: str
    """The stable identity key.

    Never the email. Email addresses are mutable and reassignable, so keying
    principals on one means a renamed or recycled address silently inherits or
    loses grants — and PM-11 access review stops being sound. Email below is a
    display attribute and nothing more.
    """

    email: str
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None

    channel: AuthChannel = "iap"
    """How this identity was established.

    A first-class field rather than a flag buried in claims, because PM-7
    requires every audit record to name the authentication channel. A
    dev-bypassed request must never be indistinguishable downstream from a real
    session.
    """

    auth_time: int | None = None
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_bypass(self) -> bool:
        return self.channel == "dev-bypass"
