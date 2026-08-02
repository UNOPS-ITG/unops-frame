"""The BigQuery connector's consent flow.

The state check is the substance. Everything else is URL construction, and the
parameters that matter are the ones whose absence produces a connector that
works during testing and stops later.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from lib.corporate.consent import (
    POPUP_RETURN,
    ConsentRejected,
    build_consent_url,
    new_state,
    verify_state,
)
from lib.corporate.tokens import BIGQUERY_SCOPE

DRIVE = "https://www.googleapis.com/auth/drive.readonly"


def params(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def consent(granted: tuple[str, ...] = (), subject: str = "u1") -> str:
    return build_consent_url(
        client_id="frame.apps.googleusercontent.com",
        redirect_uri="https://frame.unops.org/api/v1/corporate/connection/callback",
        required_scopes=[BIGQUERY_SCOPE],
        granted_scopes=granted,
        state=new_state(subject),
    ).url


# --- what the consent screen asks for -------------------------------------


def test_only_the_missing_scope_is_requested() -> None:
    """A user who already connected another Google surface sees a screen listing
    one new permission rather than a re-confirmation of everything — which is
    less alarming and less likely to be declined out of caution."""
    assert params(consent(granted=(DRIVE,)))["scope"] == BIGQUERY_SCOPE


def test_already_granted_scopes_are_carried_forward() -> None:
    """Google returns a token carrying the union. Omitting this is how
    connecting a second connector silently breaks the first."""
    assert params(consent())["include_granted_scopes"] == "true"


def test_offline_access_is_requested() -> None:
    """Without it Google issues no refresh token, and the connector works until
    the first access token expires an hour later — exactly long enough to pass a
    manual test."""
    assert params(consent())["access_type"] == "offline"


def test_consent_is_forced() -> None:
    """Google omits the refresh token on a repeat grant it considers already
    given. A connector that stores none stops working silently, and the user
    cannot fix it without revoking Frame in their Google account first."""
    assert params(consent())["prompt"] == "consent"


def test_a_flow_with_nothing_to_ask_for_is_refused() -> None:
    """The caller should have checked. Sending someone to a consent screen that
    offers nothing, with prompt=consent, produces a pointless re-grant."""
    with pytest.raises(ValueError, match="nothing to consent to"):
        build_consent_url(
            client_id="c", redirect_uri="r",
            required_scopes=[BIGQUERY_SCOPE], granted_scopes=(BIGQUERY_SCOPE,),
            state=new_state("u1"),
        )


# --- the state check ------------------------------------------------------


def test_a_matching_callback_is_accepted() -> None:
    state = new_state("u1")
    request = build_consent_url(
        client_id="c", redirect_uri="r", required_scopes=[BIGQUERY_SCOPE],
        granted_scopes=(), state=state,
    )
    returned = params(request.url)["state"]

    assert verify_state(
        returned_state=returned,
        cookie_state=request.state_cookie_value,
        authenticated_subject="u1",
    ) == POPUP_RETURN


def test_a_callback_with_no_cookie_is_refused() -> None:
    """This browser did not start a flow."""
    with pytest.raises(ConsentRejected, match="no consent flow"):
        verify_state(returned_state="abc:u1|x", cookie_state=None, authenticated_subject="u1")


def test_a_callback_whose_state_does_not_match_the_cookie_is_refused() -> None:
    """This callback does not belong to that flow."""
    with pytest.raises(ConsentRejected, match="does not match"):
        verify_state(
            returned_state="forged:u1|x",
            cookie_state=new_state("u1"),
            authenticated_subject="u1",
        )


def test_one_persons_consent_cannot_land_on_anothers_account() -> None:
    """The hole a random nonce alone leaves open.

    A nonce proves the callback follows a request Frame made; it does not prove
    it follows a request THIS user made. Reachable by handing someone a crafted
    link, and invisible afterwards — the tokens simply belong to the wrong
    person. Frame's callback is authenticated, so the subject can be compared
    rather than resolved after the fact.
    """
    state = new_state("maya")
    with pytest.raises(ConsentRejected, match="different account"):
        verify_state(
            returned_state=f"{state}|{POPUP_RETURN}",
            cookie_state=state,
            authenticated_subject="sam",
        )


def test_the_subject_is_carried_in_the_state_rather_than_looked_up() -> None:
    """So the check is a comparison. A lookup after the fact is the version that
    resolves whoever happens to be signed in."""
    state = new_state("maya@unops.org")
    assert state.endswith(":maya@unops.org")


def test_a_subject_containing_a_colon_still_binds_correctly() -> None:
    """The dev bypass prefixes subjects with `dev-bypass:`, so a naive split on
    the first colon would compare against the wrong half and refuse every local
    consent."""
    subject = "dev-bypass:maya@unops.org"
    state = new_state(subject)

    assert verify_state(
        returned_state=f"{state}|{POPUP_RETURN}",
        cookie_state=state,
        authenticated_subject=subject,
    ) == POPUP_RETURN
