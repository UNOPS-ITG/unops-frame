"""HTTP exception taxonomy.

The ``extra`` dict is splatted into the response body by the handler. That is
the mechanism PM-5a needs: a 403 can carry a machine-readable explanation
object — the deciding rule's name, the Blueprint, the steward to ask — beside
``detail``, without a bespoke response model per failure and without any
component reasoning about rules a second time.
"""

from __future__ import annotations

from typing import Any


class APIException(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.detail
        self.status_code = status_code or self.status_code
        self.headers = headers
        self.extra = extra or {}
        super().__init__(self.detail)


class AuthenticationError(APIException):
    status_code = 401
    detail = "Not authenticated"


class AuthorizationError(APIException):
    """403. Raised only by callers of the permission library, carrying a Decision."""

    status_code = 403
    detail = "Access denied"


class NotFoundError(APIException):
    status_code = 404
    detail = "Not found"


class RequestValidationError(APIException):
    status_code = 400
    detail = "Invalid request"


class ConflictError(APIException):
    status_code = 409
    detail = "Conflict"


class PreconditionFailedError(APIException):
    """412. Optimistic concurrency: the client's field version is stale (GR-8)."""

    status_code = 412
    detail = "Precondition failed"


class LifecycleError(APIException):
    """409, but specifically PM-12: frozen, submitted, or under legal hold.

    Distinct from ConflictError for two reasons: the response must NAME the
    governing mechanism so the user knows whether to wait or to amend, and a
    generic 409 gets retried by well-behaved clients while this one never
    should be.
    """

    status_code = 409
    detail = "Rejected by a lifecycle rule"


class PayloadTooLargeError(APIException):
    status_code = 413
    detail = "Request body too large"


class RateLimitError(APIException):
    status_code = 429
    detail = "Too many requests"


class UpstreamUnavailableError(APIException):
    """503. An identity provider or the warehouse could not be reached.

    Never conflated with a 401: "we could not check" and "we checked and you
    may not" are different facts, and telling a user the second when the first
    is true sends them to reset a password that was never the problem.
    """

    status_code = 503
    detail = "Upstream dependency unavailable"
