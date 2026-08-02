"""Logging configuration.

Four rules, each of which exists because breaking it has cost somebody a day.

**Never call ``basicConfig`` when a handler already exists.** Managed runtimes
install their own handler and set the root logger to WARNING; calling
``basicConfig`` there is a no-op, so every INFO line vanishes in exactly the
environment where you need them and works fine on your laptop.

**Never f-strings in log calls.** ``logger.info("row=%s", row_id)``, not
``logger.info(f"row={row_id}")``. Beyond the usual cost argument, lazy
interpolation means a DEBUG line containing row values is never *materialised*
in production — which narrows the surface for a trimmed field leaking into a
log aggregator that has no idea it was meant to be withheld.

**A logging call must never be able to raise.** Never hand a logger an object
whose serialisation can fail.

**Silence the libraries.** Google's auth stack and the HTTP clients are chatty
at INFO and drown our own lines.
"""

from __future__ import annotations

import logging

from api.core.config import Settings
from api.core.correlation import get_correlation_id

_NOISY = ("google.auth", "google.api_core", "urllib3", "httpx", "httpcore", "asyncio")


class _CorrelationFilter(logging.Filter):
    """Puts the request's correlation id on every record.

    A filter rather than a formatter argument so that library log lines emitted
    during a request also carry it — those are the ones you most want tied to a
    request when something fails deep in a client.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()

    if root.handlers:
        # Someone else owns the handler. Adjust the level rather than stacking a
        # second handler, which would duplicate every line.
        root.setLevel(level)
        for handler in root.handlers:
            handler.addFilter(_CorrelationFilter())
    else:
        handler = logging.StreamHandler()
        handler.addFilter(_CorrelationFilter())
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s [%(correlation_id)s] %(name)s: %(message)s"
            )
        )
        root.addHandler(handler)
        root.setLevel(level)

    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)
