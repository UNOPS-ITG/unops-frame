"""The BigQuery connector's token store.

Follows `ai-bob`'s proven pattern — IAP-inbound and user-OAuth-outbound already
coexist in production there, which is precisely Frame's combination — and closes
four gaps the estate leaves open. Each is called out because each is a real
defect that a straight copy would inherit.

**1. The access token is cached.** `ai-bob`'s Google path does a KMS decrypt
plus an OAuth round-trip on *every call*. That is fine for Drive metadata and
unacceptable on a query path: it roughly doubles the latency of the thing it is
protecting, and at ~300–400ms per BigQuery query the overhead is the user-visible
part. The pattern copied here is the *Atlassian* branch of the same file, which
gets it right — per-principal lock, double-checked cache, expiry skew.

**2. `invalid_grant` never overwrites the store.** A dead refresh token means
reconnect; writing anything in response to that error is what turns a recoverable
"please reconnect" into a connector that cannot be repaired.

**3. Disconnect actually revokes.** Nothing in the estate revokes an OAuth token
— disconnect deletes the local copy and leaves a live grant on Google. Once
queries run as the user that is a compliance question rather than a nicety.

**4. Tokens are keyed on the SUBJECT, never the email.** `ai-bob` stores at
`users/{email}/tokens/{provider}`. An address is mutable and reassignable, so a
renamed or recycled address silently inherits or loses a credential that reads
corporate data as its owner. PM-11 access review is unsound if that can happen.

The cross-instance race is *not* closed: two processes refreshing the same
principal concurrently can still both call Google. Google does not rotate
refresh tokens on use, so the outcome is a wasted round-trip rather than a
broken connector — which is why this is documented and not built. Atlassian,
which does rotate, would need a Firestore lease.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lib.corporate.crypto import Cipher
from lib.corporate.executor import Credential

logger = logging.getLogger(__name__)

PROVIDER = "bigquery"
BIGQUERY_SCOPE = "https://www.googleapis.com/auth/bigquery.readonly"
"""Read-only, and that is the whole grant.

Frame never writes to the warehouse. Asking for `bigquery` rather than
`bigquery.readonly` would put a consent screen in front of every user saying
Frame may modify their data, which is both untrue and the kind of over-ask that
makes people decline the whole connector.
"""

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a URL, not a secret
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

EXPIRY_SKEW_SECONDS = 300
"""Treat a token as expired five minutes early.

A token that expires mid-query fails the query, not the refresh — and the user
sees a corporate-data error with no obvious cause.
"""


class ReconnectRequired(RuntimeError):
    """The stored grant is dead. The user must consent again.

    Distinct from a transient failure on purpose: the correct response is a
    "reconnect" prompt, and retrying instead produces a loop that never succeeds.
    """


@dataclass(frozen=True, slots=True)
class StoredGrant:
    subject: str
    encrypted_refresh_token: str
    scopes: tuple[str, ...]
    granted_at: str
    email: str | None = None
    """Recorded for display only. Never used as a key — see the module docstring."""

    def has(self, scope: str) -> bool:
        return scope in self.scopes


class TokenStore:
    """Reads and writes grants; mints and caches access tokens."""

    def __init__(
        self,
        db: Any,
        cipher: Cipher,
        *,
        client_id: str,
        client_secret: str,
        http_post: Any | None = None,
    ) -> None:
        self._db = db
        self._cipher = cipher
        self._client_id = client_id
        self._client_secret = client_secret
        # Injected so the refresh path is testable without a network. The
        # default is resolved lazily to keep httpx out of the import graph of
        # anything that only reads grants.
        self._post = http_post

        self._cache: dict[str, tuple[str, float]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # --- storage ----------------------------------------------------------

    def _document(self, subject: str) -> Any:
        from lib.paths import CONNECTORS, USERS

        return (
            self._db.collection(USERS)
            .document(subject)
            .collection(CONNECTORS)
            .document(PROVIDER)
        )

    def store(self, subject: str, refresh_token: str, scopes: list[str], email: str | None = None) -> None:
        self._document(subject).set(
            {
                "subject": subject,
                "email": email,
                "encryptedRefreshToken": self._cipher.encrypt(refresh_token),
                "grantedScopes": sorted(set(scopes)),
                "grantedAt": datetime.now(UTC).isoformat(),
                "provider": PROVIDER,
            },
            merge=True,
        )
        # A new refresh token invalidates any cached access token minted from
        # the old one — which after a scope upgrade is the difference between
        # the new scope working and it silently not.
        self._forget(subject)

    def get(self, subject: str) -> StoredGrant | None:
        snapshot = self._document(subject).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        ciphertext = data.get("encryptedRefreshToken")
        if not ciphertext:
            return None
        return StoredGrant(
            subject=subject,
            encrypted_refresh_token=ciphertext,
            scopes=tuple(data.get("grantedScopes", ())),
            granted_at=str(data.get("grantedAt", "")),
            email=data.get("email"),
        )

    def granted_scopes(self, subject: str) -> tuple[str, ...]:
        grant = self.get(subject)
        return grant.scopes if grant else ()

    def is_connected(self, subject: str) -> bool:
        """Whether this principal can read corporate data at all.

        Requires the scope, not merely a stored grant: a user who connected for
        a different Google connector has a refresh token and no BigQuery access,
        and treating that as connected produces a 403 from Google that reads as
        a Frame bug.
        """
        return BIGQUERY_SCOPE in self.granted_scopes(subject)

    # --- access tokens ----------------------------------------------------

    def _lock_for(self, subject: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(subject)
            if lock is None:
                lock = threading.Lock()
                self._locks[subject] = lock
            return lock

    def _cached(self, subject: str) -> str | None:
        entry = self._cache.get(subject)
        if entry and entry[1] > time.time():
            return entry[0]
        return None

    def _forget(self, subject: str) -> None:
        self._cache.pop(subject, None)

    def credential(self, subject: str) -> Credential | None:
        """A usable access token for this principal, or None if not connected.

        Cached and serialised per principal. Without the cache this is a KMS
        decrypt plus an OAuth round-trip on the path of every corporate-data
        read, which at BigQuery's ~300–400ms best case is the part the user
        actually feels.
        """
        if not self.is_connected(subject):
            return None

        token = self._cached(subject)
        if token:
            return Credential(access_token=token, subject=subject)

        with self._lock_for(subject):
            # Another thread may have refreshed while this one waited.
            token = self._cached(subject)
            if token:
                return Credential(access_token=token, subject=subject)

            grant = self.get(subject)
            if grant is None:
                return None

            refresh_token = self._cipher.decrypt(grant.encrypted_refresh_token)
            access_token, expires_in = self._refresh(subject, refresh_token)
            self._cache[subject] = (
                access_token,
                time.time() + max(expires_in - EXPIRY_SKEW_SECONDS, 60),
            )
            return Credential(access_token=access_token, subject=subject)

    def _refresh(self, subject: str, refresh_token: str) -> tuple[str, int]:
        response = self._http_post(
            GOOGLE_TOKEN_URL,
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if response.status_code == 400 and "invalid_grant" in response.text:
            # The grant is dead — revoked upstream, or the user removed Frame
            # from their account. Nothing is written: a stale write here is what
            # turns "please reconnect" into a connector that cannot be repaired.
            logger.warning(
                "BigQuery refresh token rejected for subject %s — reconnect required", subject
            )
            raise ReconnectRequired(
                "Your BigQuery connection has expired. Reconnect it to read corporate data."
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"BigQuery token refresh failed with {response.status_code}. This is a "
                "transient failure rather than a dead grant; the stored token is untouched."
            )

        data = response.json()
        return str(data["access_token"]), int(data.get("expires_in") or 3600)

    # --- disconnecting ----------------------------------------------------

    def disconnect(self, subject: str) -> bool:
        """Revoke at Google, then delete locally.

        In that order, and both. Deleting the local copy alone — which is what
        the estate does today — leaves a live grant on the user's Google account
        that Frame can no longer see and the user believes is gone. Once queries
        run as the user, that is a compliance question rather than a nicety.

        Returns whether the upstream revocation succeeded. Local deletion happens
        regardless: a user who asked to disconnect must not stay connected
        because Google was unreachable.
        """
        grant = self.get(subject)
        self._forget(subject)

        revoked = False
        if grant is not None:
            try:
                refresh_token = self._cipher.decrypt(grant.encrypted_refresh_token)
                response = self._http_post(GOOGLE_REVOKE_URL, {"token": refresh_token})
                revoked = response.status_code == 200
                if not revoked:
                    logger.warning(
                        "Google refused to revoke the BigQuery grant for subject %s (%s). "
                        "The local record is still removed; the grant may remain live "
                        "and should be checked.",
                        subject, response.status_code,
                    )
            except Exception:  # noqa: BLE001 - never block a disconnect
                logger.exception("Revoking the BigQuery grant failed for subject %s", subject)

        self._document(subject).delete()
        return revoked

    # --- transport --------------------------------------------------------

    def _http_post(self, url: str, data: dict[str, str]) -> Any:
        if self._post is not None:
            return self._post(url, data)
        import httpx

        return httpx.post(url, data=data, timeout=15.0)
