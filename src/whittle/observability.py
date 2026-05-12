"""Optional Logfire observability wiring for the local planning demo."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_CONFIGURED = False
_FASTAPI_INSTRUMENTED = False


def logfire_enabled() -> bool:
    """Return whether Logfire instrumentation is enabled for this process."""

    return os.getenv("WHITTLE_LOGFIRE_ENABLED", "").lower() in {"1", "true", "yes", "on"}


def configure_observability(app: FastAPI | None = None) -> None:
    """Configure Logfire once, then instrument supported libraries.

    Instrumentation is opt-in so local development keeps working without a
    Logfire token. Set `WHITTLE_LOGFIRE_ENABLED=true` and `LOGFIRE_TOKEN=...`
    to send traces to the graphical Logfire UI.
    """

    if not logfire_enabled():
        return

    try:
        import logfire
    except ImportError:
        return

    global _CONFIGURED, _FASTAPI_INSTRUMENTED

    if not _CONFIGURED:
        logfire.configure(
            service_name="whittle",
            environment=os.getenv("WHITTLE_ENVIRONMENT", os.getenv("APP_ENV", "local")),
            send_to_logfire="if-token-present",
            console=False,
        )
        logfire.instrument_pydantic_ai()
        _CONFIGURED = True

    if app is not None and not _FASTAPI_INSTRUMENTED:
        logfire.instrument_fastapi(app)
        _FASTAPI_INSTRUMENTED = True
