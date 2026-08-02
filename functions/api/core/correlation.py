"""The request correlation id.

PM-7 requires every audit record to carry one, and AU-8 requires the same id on
the domain event, so a write, its audit entry and the event it published can be
tied together after the fact. A ContextVar rather than a parameter threaded
through every call because the row writer, the permission library and the
outbox are reached through several layers that have no business knowing about
HTTP.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("frame_correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(value: str) -> object:
    """Returns the token needed to reset it; the middleware always resets."""
    return _correlation_id.set(value)


def reset_correlation_id(token: object) -> None:
    _correlation_id.reset(token)  # type: ignore[arg-type]


def get_correlation_id() -> str | None:
    return _correlation_id.get()
