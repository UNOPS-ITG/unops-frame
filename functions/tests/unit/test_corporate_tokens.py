"""The BigQuery connector's token store.

Most of these are the four gaps a straight copy of the estate's pattern would
inherit. Each is a real defect there, so each gets a test here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import pytest

from lib.corporate.crypto import DecryptionRefused, LocalDevCipher, build_cipher
from lib.corporate.tokens import (
    BIGQUERY_SCOPE,
    ReconnectRequired,
    TokenStore,
)
from tests.fakes.firestore import FakeFirestore

SUBJECT = "u1"
OTHER_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict[str, Any]
    text: str = ""

    def json(self) -> dict[str, Any]:
        return self.payload


class FakePost:
    """Records every call so the tests can assert what did and did not happen."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, data: dict[str, str]) -> FakeResponse:
        self.calls.append((url, data))
        return self.responses.pop(0) if self.responses else FakeResponse(200, {})


def store(db: FakeFirestore, post: Any = None) -> TokenStore:
    return TokenStore(
        db, LocalDevCipher(), client_id="cid", client_secret="secret", http_post=post
    )


@pytest.fixture
def db() -> FakeFirestore:
    return FakeFirestore()


def connect(s: TokenStore, scopes: list[str] | None = None) -> None:
    s.store(SUBJECT, "refresh-token-1", scopes or [BIGQUERY_SCOPE], email="maya@unops.org")


# --- keyed on the subject, never the email --------------------------------


def test_a_grant_is_stored_under_the_subject_not_the_email(db: FakeFirestore) -> None:
    """An address is mutable and reassignable, so keying a credential that reads
    corporate data as its owner on one means a renamed or recycled address
    inherits it — and PM-11 access review stops being sound."""
    connect(store(db))

    assert f"users/{SUBJECT}/connectors/bigquery" in db.docs
    assert not any("maya@unops.org" in path for path in db.docs)


def test_the_email_is_kept_for_display_only(db: FakeFirestore) -> None:
    s = store(db)
    connect(s)
    grant = s.get(SUBJECT)

    assert grant is not None
    assert grant.email == "maya@unops.org"
    assert grant.subject == SUBJECT


def test_the_refresh_token_is_never_stored_in_plaintext(db: FakeFirestore) -> None:
    connect(store(db))
    stored = db.docs[f"users/{SUBJECT}/connectors/bigquery"]

    assert "refresh-token-1" not in str(stored)
    assert stored["encryptedRefreshToken"].startswith("local-dev:v1:")


# --- connected means "has the scope", not "has a token" -------------------


def test_a_grant_without_the_bigquery_scope_is_not_connected(db: FakeFirestore) -> None:
    """A user who connected a different Google connector has a refresh token and
    no BigQuery access. Treating that as connected produces a 403 from Google
    that reads as a Frame bug."""
    s = store(db)
    s.store(SUBJECT, "rt", [OTHER_SCOPE])

    assert s.is_connected(SUBJECT) is False
    assert s.credential(SUBJECT) is None


def test_the_scope_is_read_only(db: FakeFirestore) -> None:
    """Frame never writes to the warehouse. Asking for `bigquery` would put a
    consent screen in front of every user saying Frame may modify their data,
    which is untrue and the kind of over-ask that makes people decline."""
    assert BIGQUERY_SCOPE.endswith("bigquery.readonly")


def test_an_unconnected_principal_gets_no_credential(db: FakeFirestore) -> None:
    assert store(db).credential("nobody") is None


# --- gap 1: the access token is cached ------------------------------------


def test_an_access_token_is_minted_once_and_reused(db: FakeFirestore) -> None:
    """The estate's Google path does a KMS decrypt plus an OAuth round-trip on
    every call. At BigQuery's ~300-400ms best case that overhead is the part the
    user feels."""
    post = FakePost(FakeResponse(200, {"access_token": "at-1", "expires_in": 3600}))
    s = store(db, post)
    connect(s)

    first = s.credential(SUBJECT)
    second = s.credential(SUBJECT)

    assert first is not None and second is not None
    assert first.access_token == second.access_token == "at-1"
    assert len(post.calls) == 1, "the second call should have been served from cache"


def test_concurrent_callers_mint_one_token_between_them(db: FakeFirestore) -> None:
    """Serialised per principal. Without the lock, ten grid cells resolving at
    once produce ten refreshes."""
    post = FakePost(*[FakeResponse(200, {"access_token": f"at-{i}", "expires_in": 3600}) for i in range(10)])
    s = store(db, post)
    connect(s)

    tokens: list[str] = []
    barrier = threading.Barrier(8)

    def resolve() -> None:
        barrier.wait()
        credential = s.credential(SUBJECT)
        if credential:
            tokens.append(credential.access_token)

    threads = [threading.Thread(target=resolve) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(tokens)) == 1, f"expected one token, got {set(tokens)}"
    assert len(post.calls) == 1


def test_a_cached_token_is_dropped_when_the_grant_is_replaced(db: FakeFirestore) -> None:
    """After a scope upgrade the old token lacks the new scope, so serving it
    from cache is the difference between the new scope working and it silently
    not."""
    post = FakePost(
        FakeResponse(200, {"access_token": "at-old", "expires_in": 3600}),
        FakeResponse(200, {"access_token": "at-new", "expires_in": 3600}),
    )
    s = store(db, post)
    connect(s)
    assert s.credential(SUBJECT).access_token == "at-old"  # type: ignore[union-attr]

    s.store(SUBJECT, "refresh-token-2", [BIGQUERY_SCOPE, OTHER_SCOPE])
    assert s.credential(SUBJECT).access_token == "at-new"  # type: ignore[union-attr]


def test_the_cache_expires_early(db: FakeFirestore) -> None:
    """A token that expires mid-query fails the query, not the refresh, and the
    user sees a corporate-data error with no obvious cause."""
    post = FakePost(
        FakeResponse(200, {"access_token": "at-1", "expires_in": 60}),
        FakeResponse(200, {"access_token": "at-2", "expires_in": 3600}),
    )
    s = store(db, post)
    connect(s)

    # expires_in 60 is below the 300s skew, so the floor applies and the token
    # is still cached — but a *second* call after it lapses must re-mint.
    assert s.credential(SUBJECT).access_token == "at-1"  # type: ignore[union-attr]
    s._cache[SUBJECT] = ("at-1", 0.0)  # force the lapse rather than sleeping
    assert s.credential(SUBJECT).access_token == "at-2"  # type: ignore[union-attr]


# --- gap 2: invalid_grant never overwrites --------------------------------


def test_a_dead_grant_asks_for_a_reconnect_and_writes_nothing(db: FakeFirestore) -> None:
    """Writing anything in response to invalid_grant is what turns a recoverable
    "please reconnect" into a connector that cannot be repaired."""
    post = FakePost(FakeResponse(400, {}, text='{"error": "invalid_grant"}'))
    s = store(db, post)
    connect(s)
    before = dict(db.docs[f"users/{SUBJECT}/connectors/bigquery"])

    with pytest.raises(ReconnectRequired):
        s.credential(SUBJECT)

    assert db.docs[f"users/{SUBJECT}/connectors/bigquery"] == before


def test_a_transient_failure_is_not_reported_as_a_dead_grant(db: FakeFirestore) -> None:
    """The correct response differs: reconnect versus retry. Conflating them
    tells a user to re-consent because Google had a bad minute."""
    post = FakePost(FakeResponse(503, {}, text="upstream unavailable"))
    s = store(db, post)
    connect(s)

    with pytest.raises(RuntimeError) as exc:
        s.credential(SUBJECT)
    assert not isinstance(exc.value, ReconnectRequired)


# --- gap 3: disconnect revokes --------------------------------------------


def test_disconnect_revokes_at_google_before_deleting_locally(db: FakeFirestore) -> None:
    """Deleting the local copy alone leaves a live grant on the user's account
    that Frame can no longer see and the user believes is gone."""
    post = FakePost(FakeResponse(200, {}))
    s = store(db, post)
    connect(s)

    assert s.disconnect(SUBJECT) is True
    assert post.calls[0][0].endswith("/revoke")
    assert post.calls[0][1]["token"] == "refresh-token-1"
    assert f"users/{SUBJECT}/connectors/bigquery" not in db.docs


def test_disconnect_removes_the_local_record_even_if_revocation_fails(
    db: FakeFirestore,
) -> None:
    """A user who asked to disconnect must not stay connected because Google was
    unreachable."""
    post = FakePost(FakeResponse(500, {}, text="nope"))
    s = store(db, post)
    connect(s)

    assert s.disconnect(SUBJECT) is False
    assert f"users/{SUBJECT}/connectors/bigquery" not in db.docs


def test_disconnect_clears_the_cached_access_token(db: FakeFirestore) -> None:
    """Otherwise a disconnected user keeps reading corporate data until the
    cache lapses."""
    post = FakePost(
        FakeResponse(200, {"access_token": "at-1", "expires_in": 3600}),
        FakeResponse(200, {}),
    )
    s = store(db, post)
    connect(s)
    s.credential(SUBJECT)

    s.disconnect(SUBJECT)
    assert s.credential(SUBJECT) is None


def test_disconnecting_something_never_connected_is_not_an_error(db: FakeFirestore) -> None:
    assert store(db, FakePost()).disconnect("nobody") is False


# --- the cipher gate ------------------------------------------------------


def test_a_deployed_process_refuses_to_run_without_kms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three gates, any one of which fails closed — the same shape as the dev
    auth bypass. A fallback one misread variable away from production is a
    latent incident, not a fallback."""
    with pytest.raises(RuntimeError, match="Refusing to start"):
        build_cipher(environment="production", kms_key_name=None)

    monkeypatch.setenv("K_SERVICE", "frame-api")
    with pytest.raises(RuntimeError, match="Refusing to start"):
        build_cipher(environment="local", kms_key_name=None)


def test_local_encryption_is_allowed_only_locally() -> None:
    cipher = build_cipher(environment="local", kms_key_name=None)
    assert cipher.decrypt(cipher.encrypt("secret")) == "secret"


def test_a_locally_encrypted_value_is_marked_as_such() -> None:
    """So "this was encrypted locally" is a fact the reader can check rather
    than an assumption, and a deployed process refuses it instead of failing in
    a way that looks like corruption."""
    value = LocalDevCipher().encrypt("secret")
    assert value.startswith("local-dev:v1:")

    with pytest.raises(DecryptionRefused):
        LocalDevCipher().decrypt("kms:v1:AAAA")
