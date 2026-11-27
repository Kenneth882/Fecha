"""arq jobs and the worker's configuration.

Run the worker with `arq app.workers.tasks.WorkerSettings`.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from anthropic import AsyncAnthropic
from arq import func
from arq.connections import RedisSettings

from app.core.config import Settings, load_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.services.claude_content_generator import ClaudeContentGenerator
from app.services.content_generation import fill_event_content
from app.services.content_generator import ContentGenerator, OffContentGenerator

logger = logging.getLogger(__name__)


async def noop(ctx: dict[str, Any]) -> None:
    """Does nothing. It proves a job can travel from the queue through the worker."""


async def generate_event_content(ctx: dict[str, Any], event_id: uuid.UUID | str) -> dict[str, int]:
    """Fill the shared content for the Event's Scenarios at its language and Level, and
    return how many attempts ended each way. Queued by `POST /events` (see
    `app.workers.queue`); never changes the schedule (ADR 0004)."""
    settings: Settings = ctx["settings"]
    now = ctx.get("now", _utc_now)
    async with ctx["session_factory"]() as session:
        outcomes = await fill_event_content(
            session,
            ctx["redis"],
            ctx["generator"],
            uuid.UUID(str(event_id)),
            daily_budget_usd=settings.llm_daily_budget_usd,
            now=now,
        )
    summary = {str(outcome): count for outcome, count in outcomes.items()}
    logger.info("generated the Event's content", extra={"event_id": str(event_id), **summary})
    return summary


def _utc_now() -> datetime:
    return datetime.now(UTC)


def anthropic_client(settings: Settings) -> AsyncAnthropic | None:
    """The Anthropic client for these settings, or None when there's no API key."""
    if settings.anthropic_api_key is None:
        return None
    return AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())


def content_generator(settings: Settings, client: AsyncAnthropic | None) -> ContentGenerator:
    """The content generator for these settings: Claude when there's a client (an API
    key is set), else "off". Logs when generation is off."""
    if client is None:
        logger.warning(
            "content generation is off: ANTHROPIC_API_KEY is not set, so Listen Tasks "
            "use the hand-written fallbacks"
        )
        return OffContentGenerator()
    logger.info("content generation is on", extra={"model": settings.llm_model})
    return ClaudeContentGenerator(client, settings.llm_model)


async def startup(ctx: dict[str, Any]) -> None:
    """Open the DB engine and, with an API key, the Anthropic client the jobs use."""
    settings: Settings = ctx["settings"]
    engine = create_engine(settings)
    ctx["engine"] = engine
    ctx["session_factory"] = create_session_factory(engine)
    client = anthropic_client(settings)
    ctx["anthropic_client"] = client
    ctx["generator"] = content_generator(settings, client)


async def shutdown(ctx: dict[str, Any]) -> None:
    client: AsyncAnthropic | None = ctx.get("anthropic_client")
    if client is not None:
        await client.close()
    await ctx["engine"].dispose()


def worker_settings(settings: Settings) -> dict[str, Any]:
    """The arq Worker's keyword arguments for these settings."""
    return {
        # No kept result, so the Event's job ID is free again as soon as it finishes
        # and a Re-plan can queue the job again.
        "functions": [noop, func(generate_event_content, keep_result=0)],
        "redis_settings": RedisSettings.from_dsn(settings.redis_url.get_secret_value()),
        "ctx": {"settings": settings},
        "on_startup": startup,
        "on_shutdown": shutdown,
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
