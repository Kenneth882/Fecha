"""arq jobs and the worker's configuration.

Run the worker with `arq app.workers.tasks.WorkerSettings`.
"""

from typing import Any

from arq.connections import RedisSettings

from app.core.config import Settings, load_settings
from app.core.logging import configure_logging


async def noop(ctx: dict[str, Any]) -> None:
    """Does nothing. It proves a job can travel from the queue through the worker."""


def worker_settings(settings: Settings) -> dict[str, Any]:
    """The arq Worker's keyword arguments for these settings."""
    return {
        "functions": [noop],
        "redis_settings": RedisSettings.from_dsn(settings.redis_url.get_secret_value()),
        "ctx": {"settings": settings},
    }


def __getattr__(name: str) -> Any:
    """Build `WorkerSettings` only when arq asks for it.

    arq reads this attribute on startup, which makes it the worker's composition
    root: settings are loaded here, and importing this module stays free of
    side effects (tests import the jobs without needing a full environment).
    """
    if name == "WorkerSettings":
        settings = load_settings()
        configure_logging(settings.log_level)
        return worker_settings(settings)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
