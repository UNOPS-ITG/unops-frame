"""Settings as a dependency.

Handlers read configuration from the app they belong to, never from the
module-level cache. The two diverge whenever an app is built with explicit
settings — a test, or two apps in one process — and the symptom is a handler
confidently reporting something about a configuration it is not running under.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from api.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


AppSettings = Annotated[Settings, Depends(get_app_settings)]
