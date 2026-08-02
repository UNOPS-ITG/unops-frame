"""The OAuth consent flow for the BigQuery connector.

Pure URL construction and state handling, kept out of the router so the parts
that can be wrong are testable without a browser.

**Scope-delta consent.** Frame asks only for what it does not already have, with
``include_granted_scopes=true`` so Google returns a token carrying the union. A
user who has already connected another Google surface sees a consent screen
listing one new permission rather than a re-confirmation of everything — which
is both less alarming and less likely to be declined out of caution.

**The state is bound to the principal, not merely random.** A random nonce
proves the callback follows a request Frame made; it does not prove it follows a
request *this user* made. Frame's callback arrives authenticated (it comes back
through the same IAP-protected origin), so the subject is checked against the
one the flow started for — closing a replay where one user's consent lands on
another's account. That check is available here and is not in the estate's
version, which resolves the user from a session cookie after the fact.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

STATE_COOKIE = "frame_bq_oauth_state"
STATE_MAX_AGE_SECONDS = 600
"""Ten minutes. Long enough to read a consent screen, short enough that an
abandoned flow cannot be resumed from a shared machine an hour later."""

POPUP_RETURN = "__popup__"


class ConsentRejected(ValueError):
    """The callback does not match the request that started the flow."""


@dataclass(frozen=True, slots=True)
class ConsentRequest:
    url: str
    state_cookie_value: str


def new_state(subject: str) -> str:
    """A nonce bound to the principal the flow is for.

    Stored in a cookie and echoed through Google's `state` parameter, then
    checked against BOTH on return. The subject is in the value rather than
    inferred later so the check is a comparison rather than a lookup.
    """
    return f"{secrets.token_urlsafe(32)}:{subject}"


def build_consent_url(
    *,
    client_id: str,
    redirect_uri: str,
    required_scopes: list[str],
    granted_scopes: tuple[str, ...],
    state: str,
    return_to: str = POPUP_RETURN,
) -> ConsentRequest:
    """Where to send the user, asking only for what is missing."""
    delta = sorted(set(required_scopes) - set(granted_scopes))
    if not delta:
        raise ValueError("nothing to consent to — the caller should not have started a flow")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(delta),
        # Google returns a token carrying the UNION of old and new scopes, so a
        # user connecting BigQuery does not lose a Drive connector they already
        # granted. Omitting this is how a second connector silently breaks the
        # first.
        "include_granted_scopes": "true",
        # Without offline access Google issues no refresh token, and the
        # connector works until the first access token expires an hour later —
        # which is exactly long enough to pass a manual test.
        "access_type": "offline",
        # Forced, because Google omits the refresh token on a repeat grant it
        # considers already given. A connector that stores no refresh token is
        # one that silently stops working, and the user has no way to fix it
        # except to revoke Frame in their Google account first.
        "prompt": "consent",
        "state": f"{state}|{return_to}",
    }
    return ConsentRequest(
        url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}",
        state_cookie_value=state,
    )


def verify_state(
    *, returned_state: str, cookie_state: str | None, authenticated_subject: str
) -> str:
    """Check the callback and return where to send the user next.

    Three things have to agree, and each catches something the others do not:
    the cookie (this browser started a flow), the returned parameter (this
    callback belongs to that flow), and the authenticated subject (this is the
    person the flow was for).
    """
    if not cookie_state:
        raise ConsentRejected(
            "no consent flow is in progress in this browser. Start the connection again."
        )

    state, _, return_to = returned_state.partition("|")

    # Constant-time, because a nonce comparison that leaks length or prefix is a
    # nonce comparison worth attacking.
    if not hmac.compare_digest(state, cookie_state):
        raise ConsentRejected("this callback does not match the request that started it")

    # The FIRST colon, not the last. The nonce is url-safe base64 and contains
    # none; a subject may contain several — the dev bypass prefixes with
    # `dev-bypass:`, and a Google `sub` will not. Splitting on the last colon
    # therefore works in production and refuses every local consent, which is
    # the distribution most likely to end with someone loosening the check.
    _, _, bound_subject = state.partition(":")
    if not hmac.compare_digest(bound_subject, authenticated_subject):
        # One user's consent landing on another's account. Reachable by handing
        # someone a crafted link, and invisible afterwards: the tokens simply
        # belong to the wrong person.
        raise ConsentRejected(
            "this consent was started by a different account. Start the connection again."
        )

    return return_to or POPUP_RETURN
