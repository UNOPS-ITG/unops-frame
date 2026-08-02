"""Application settings.

Two rules this module exists to hold.

**Ports are not duplicated.** ``config/ports.json`` at the repo root is the
single source of truth for every port Frame binds, shared with the frontend and
the Node tooling. Python reads that file rather than restating the numbers,
because two lists of ports drift and the symptom is a seeder writing into one
emulator while the API reads from another.

**The dev auth bypass is gated structurally, not by discipline.** See
``Settings.dev_auth_bypass_enabled``.
"""

from __future__ import annotations

import json
import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PORTS_FILE = _REPO_ROOT / "config" / "ports.json"


class Environment(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    TESTING = "testing"
    UAT = "uat"
    PRODUCTION = "production"


def _load_ports() -> dict[str, object]:
    """Read the shared port allocation, honouring the same env overrides the
    Node side honours so a shifted block stays consistent across languages."""
    raw = json.loads(_PORTS_FILE.read_text(encoding="utf-8"))
    offset = int(os.environ.get("FRAME_PORT_OFFSET", "0") or 0)

    def pick(env_name: str, default: int) -> int:
        override = os.environ.get(env_name)
        if override:
            return int(override)
        return int(default) + offset

    emulators = raw["emulators"]
    return {
        "frontend": pick("FRAME_PORT_FRONTEND", raw["frontend"]),
        "backend": pick("FRAME_PORT_BACKEND", raw["backend"]),
        "oauth_proxy": pick("FRAME_PORT_OAUTH_PROXY", raw["oauthProxy"]),
        "firestore": pick("FRAME_PORT_FIRESTORE", emulators["firestore"]),
        "auth": pick("FRAME_PORT_AUTH", emulators["auth"]),
        "pubsub": pick("FRAME_PORT_PUBSUB", emulators["pubsub"]),
        "storage": pick("FRAME_PORT_STORAGE", emulators["storage"]),
        "postgres": pick("FRAME_PORT_POSTGRES", raw["postgres"]),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("config/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL

    api_prefix: str = "/api/v1"

    # --- GCP -------------------------------------------------------------
    gcp_project_id: str = "unops-frame-dev"
    gcp_region: str = "europe-west1"

    # Named, never "(default)". A named database is what lets Frame's data live
    # beside other products in one project without sharing a namespace, and it
    # has to be set consistently everywhere or reads silently hit an empty store.
    firestore_database_id: str = "frame"

    # --- Identity --------------------------------------------------------
    # Cloud IAP signs its assertion with these. Empty in local, where
    # oauth2-proxy stands in for IAP.
    # There is deliberately no `if local:` branch in the middleware that reads
    # these. Locally the assertion is a Google OIDC id_token injected by
    # oauth2-proxy (iss accounts.google.com, RS256); deployed it is a Cloud IAP
    # assertion (iss cloud.google.com/iap, ES256). Three config values change;
    # the validation code does not, so the path exercised locally is the path
    # that runs in production.
    iap_audience: str = ""
    iap_issuer: str = "https://cloud.google.com/iap"
    iap_jwks_url: str = "https://www.gstatic.com/iap/verify/public_key-jwk"

    # Domain restriction must be enforced here and not only at the proxy.
    # Locally the audience is a public OAuth client id, so without this the
    # backend would accept an id_token from *any* Google account for that
    # client — and the dev-bypass harness proves people reach the backend port
    # directly, bypassing whatever the proxy would have checked.
    identity_hosted_domain: str = "unops.org"

    # --- Local development ----------------------------------------------
    firestore_emulator_host: str = ""
    pubsub_emulator_host: str = ""
    firebase_auth_emulator_host: str = ""
    firebase_storage_emulator_host: str = ""

    # A shared secret that lets local tooling (the agent-browser harness, e2e
    # runs) authenticate as a chosen user without the interactive OAuth dance.
    dev_auth_bypass_secret: str = ""
    dev_auth_bypass_default_email: str = ""
    # Pinned rather than arbitrary: a request header must not be able to
    # impersonate any address at all, even locally, because local runs write to
    # the same audit log shape as everything else.
    dev_auth_bypass_allowed_emails: list[str] = Field(default_factory=list)

    # --- Runtime tuning --------------------------------------------------
    # Two separate pools, and sizing one does not size the other. anyio's
    # limiter backs FastAPI's sync handlers; asyncio.to_thread uses the loop's
    # default executor, which defaults to roughly 5 threads on a small box.
    thread_limiter_tokens: int = 200
    to_thread_executor_workers: int = 64
    max_body_bytes: int = 10 * 1024 * 1024

    # --- Observability ---------------------------------------------------
    log_level: str = "INFO"

    ports: dict[str, object] = Field(default_factory=_load_ports)

    # -----------------------------------------------------------------
    @property
    def is_local(self) -> bool:
        return self.environment is Environment.LOCAL

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def running_on_cloud_run(self) -> bool:
        """Cloud Run always injects K_SERVICE. Its presence is a fact about the
        runtime rather than a configuration value, which is exactly why the
        bypass gate below keys off it: configuration can be set by mistake."""
        return bool(os.environ.get("K_SERVICE"))

    @property
    def dev_auth_bypass_enabled(self) -> bool:
        """The dev auth bypass is a genuine authentication bypass, so it is
        gated by three independent conditions rather than one flag:

        1. a secret must be configured (absent by default, and never committed),
        2. the environment must be LOCAL,
        3. the process must not be running on Cloud Run.

        Any single misconfiguration therefore fails closed. The bypass exists
        so local tooling can drive the app without an interactive OAuth flow;
        it must never be reachable from a deployed environment, and this
        property is the only place that decision is made.
        """
        return bool(self.dev_auth_bypass_secret) and self.is_local and not self.running_on_cloud_run

    @property
    def emulators_active(self) -> bool:
        return bool(self.firestore_emulator_host)

    @model_validator(mode="after")
    def _refuse_dangerous_combinations(self) -> Settings:
        if self.is_production and self.dev_auth_bypass_secret:
            raise ValueError(
                "dev_auth_bypass_secret is set in a production configuration. "
                "This is an authentication bypass; refusing to start."
            )
        if not self.is_local and self.firestore_emulator_host:
            raise ValueError(
                f"firestore_emulator_host is set in environment={self.environment}. "
                "A deployed service pointed at an emulator would silently read and "
                "write nothing; refusing to start."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
