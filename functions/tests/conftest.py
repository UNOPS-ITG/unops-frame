"""Shared test fixtures.

Every test here runs with a fully-configured Settings object built in code
rather than read from ``config/.env``: a test whose behaviour depends on a
developer's local environment file passes on one machine and fails on another,
and the failure looks like a code bug.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.config import Environment, Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """``get_settings`` is lru_cached, so a test that changes the environment
    would otherwise leak into the next one."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment=Environment.LOCAL,
        iap_audience="test-audience.apps.googleusercontent.com",
        iap_issuer="https://accounts.google.com",
        identity_hosted_domain="unops.org",
    )


@pytest.fixture
def bypass_settings() -> Settings:
    return Settings(
        environment=Environment.LOCAL,
        iap_audience="test-audience.apps.googleusercontent.com",
        dev_auth_bypass_secret="test-secret",
        dev_auth_bypass_default_email="dev@unops.org",
        dev_auth_bypass_allowed_emails=["dev@unops.org", "other@unops.org"],
    )


def build_app(settings: Settings) -> FastAPI:
    """Build an app around explicit settings.

    No monkeypatching: ``create_app`` takes settings as a parameter and threads
    them into the middleware, so a test configures the real object graph rather
    than a patched one.
    """
    from api import create_app

    return create_app(settings)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(build_app(settings)) as c:
        yield c
