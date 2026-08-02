"""Envelope encryption for stored refresh tokens.

A refresh token is a long-lived credential that reads corporate data as its
owner. It is encrypted with Cloud KMS before it reaches Firestore and decrypted
only by a dedicated impersonated principal, so a Firestore export, a backup, or
a mis-scoped read of the collection yields ciphertext.

**The local fallback is gated structurally, not by discipline.** Development
runs against emulators with no KMS, so there has to be a path that works without
it — and a path that quietly stores plaintext is worse than no path at all. So:
the fallback requires ``environment is LOCAL`` AND ``K_SERVICE`` absent, refuses
to activate otherwise, marks every value it produces with a scheme prefix, and
logs a warning at construction. A ciphertext written locally cannot be read as
KMS ciphertext and vice versa, because the prefix says which it is.
"""

from __future__ import annotations

import base64
import logging
import os
from threading import Lock
from typing import Protocol

logger = logging.getLogger(__name__)

KMS_SCHEME = "kms:v1:"
LOCAL_SCHEME = "local-dev:v1:"
"""A prefix, not a header field, so it survives any storage that stringifies.

Naming the scheme in the value is what makes "this was encrypted locally" a
fact the reader can check rather than an assumption. A deployed process that
finds a `local-dev:` value refuses it instead of failing to decrypt in a way
that looks like corruption.
"""


class Cipher(Protocol):
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...


class DecryptionRefused(RuntimeError):
    """The value cannot be decrypted here — wrong scheme, or wrong environment."""


class KmsCipher:
    """Cloud KMS envelope encryption.

    The client is built against a dedicated impersonated principal rather than
    the service's own identity, so the ability to decrypt tokens is a grant that
    can be reviewed and revoked on its own — separately from everything else the
    API can do.
    """

    def __init__(self, key_name: str, impersonate: str | None = None) -> None:
        if not key_name:
            raise ValueError("a KMS key name is required to encrypt refresh tokens")
        self._key_name = key_name
        self._impersonate = impersonate
        self._client: object | None = None
        self._lock = Lock()

    def _kms(self) -> object:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    from google.cloud import kms

                    credentials = None
                    if self._impersonate:
                        from google.auth import default, impersonated_credentials

                        source, _ = default()
                        credentials = impersonated_credentials.Credentials(
                            source_credentials=source,
                            target_principal=self._impersonate,
                            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                        )
                    self._client = kms.KeyManagementServiceClient(credentials=credentials)
        return self._client

    def encrypt(self, plaintext: str) -> str:
        response = self._kms().encrypt(  # type: ignore[attr-defined]
            request={"name": self._key_name, "plaintext": plaintext.encode("utf-8")}
        )
        return KMS_SCHEME + base64.b64encode(response.ciphertext).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith(KMS_SCHEME):
            raise DecryptionRefused(
                "this value was not encrypted with KMS. A deployed process will not "
                "read a locally-encrypted token — that would mean development "
                "credentials working in production."
            )
        raw = base64.b64decode(ciphertext[len(KMS_SCHEME) :])
        response = self._kms().decrypt(  # type: ignore[attr-defined]
            request={"name": self._key_name, "ciphertext": raw}
        )
        return str(response.plaintext.decode("utf-8"))


class LocalDevCipher:
    """Obfuscation for local development. NOT encryption, and it says so.

    There is no key management here and no secret worth protecting: the tokens
    it wraps belong to a developer who consented on their own machine against
    emulators. Base64 exists only so a token is not sitting in the emulator UI
    in plaintext where a screen share would catch it.

    Naming it honestly matters more than the mechanism. A class called
    `LocalCipher` doing base64 invites someone to reach for it in a hurry; one
    called `LocalDevCipher` that refuses to construct outside LOCAL does not.
    """

    def __init__(self) -> None:
        logger.warning(
            "CORPORATE TOKENS ARE NOT ENCRYPTED — local development only. Values are "
            "obfuscated with base64 and marked %r so they can never be read as KMS "
            "ciphertext.",
            LOCAL_SCHEME,
        )

    def encrypt(self, plaintext: str) -> str:
        return LOCAL_SCHEME + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith(LOCAL_SCHEME):
            raise DecryptionRefused(
                "this value was encrypted with KMS and cannot be read locally. "
                "Reconnect the BigQuery connector against the local environment."
            )
        return base64.b64decode(ciphertext[len(LOCAL_SCHEME) :]).decode("utf-8")


def build_cipher(
    *, environment: str, kms_key_name: str | None, impersonate: str | None = None
) -> Cipher:
    """Choose a cipher, refusing the unsafe combination outright.

    Three gates on the local path, any one of which fails closed — the same
    shape as the dev auth bypass, for the same reason: a fallback that is one
    misread environment variable away from production is not a fallback, it is a
    latent incident.
    """
    deployed = os.environ.get("K_SERVICE") is not None

    if kms_key_name:
        return KmsCipher(kms_key_name, impersonate)

    if environment != "local" or deployed:
        raise RuntimeError(
            "No KMS key is configured for corporate-data refresh tokens, and this is "
            f"not a local process (environment={environment!r}, deployed={deployed}). "
            "Refusing to start rather than storing credentials unencrypted — set "
            "FRAME_CORPORATE_KMS_KEY."
        )

    return LocalDevCipher()
