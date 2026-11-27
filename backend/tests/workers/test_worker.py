import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from arq import create_pool
from arq.connections import ArqRedis
from arq.jobs import JobStatus
from arq.worker import Worker
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.logging import configure_logging
from app.models.llm_call import LlmCall, LlmOutcome
from app.schemas.event import EventCreate
from app.schemas.user import UserCreate
from app.services.catalog import EventType
from app.services.events import create_event
from app.services.planner import Level
from app.services.users import delete_user_by_email, register_user
from app.workers.queue import ArqJobQueue
from app.workers.tasks import worker_settings
from tests.auth import GOOD_PASSWORD


async def run_burst(config: dict[str, Any], queue: str) -> Worker:
    """Run a worker on `queue` until it's empty."""
    worker = Worker(**{**config, "queue_name": queue, "burst": True})
    try:
        await worker.async_run()
    finally:
        await worker.close()
    return worker


@pytest.fixture
async def pool(settings: Settings) -> AsyncIterator[ArqRedis]:
    """An arq pool on a queue of its own, so a dev worker on the same Redis can't take
    the test's jobs."""
    pool = await create_pool(
        worker_settings(settings)["redis_settings"], default_queue_name=f"test:{uuid4()}"
    )
    yield pool
    await pool.aclose()


async def test_worker_runs_a_queued_noop_job(settings: Settings, pool: ArqRedis) -> None:
    job = await pool.enqueue_job("noop")
    assert job is not None

    worker = await run_burst(worker_settings(settings), pool.default_queue_name)

    assert await job.status() == JobStatus.complete
    assert await job.result(timeout=1) is None
    assert worker.jobs_complete == 1
    assert worker.jobs_failed == 0


async def test_an_events_content_job_is_queued_once_until_it_has_run(
    settings: Settings, pool: ArqRedis
) -> None:
    queue = ArqJobQueue(pool)
    event_id = uuid.uuid4()

    assert await queue.enqueue_event_content(event_id) is True
    assert await queue.enqueue_event_content(event_id) is False
    assert await pool.zcard(pool.default_queue_name) == 1

    # It's an unknown Event, so the job does nothing, but it runs and frees its ID.
    worker = await run_burst(worker_settings(settings), pool.default_queue_name)

    assert (worker.jobs_complete, worker.jobs_failed) == (1, 0)
    assert await queue.enqueue_event_content(event_id) is True


def log_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_without_an_api_key_the_worker_logs_once_that_generation_is_off(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    capsys.readouterr()

    worker_settings(settings)

    messages = [line["message"] for line in log_lines(capsys)]
    assert len(messages) == 1
    assert "content generation is off" in messages[0]
    assert "ANTHROPIC_API_KEY" in messages[0]


def test_a_blank_api_key_counts_as_none(settings: Settings) -> None:
    blank = Settings.model_validate({**settings.model_dump(), "anthropic_api_key": "  "})

    assert blank.anthropic_api_key is None


def test_the_llm_settings_have_their_defaults(settings: Settings) -> None:
    assert settings.anthropic_api_key is None
    assert settings.llm_model == "claude-sonnet-5-5"
    assert settings.llm_daily_budget_usd == 2


@pytest.fixture
async def committed_event(test_engine: AsyncEngine) -> AsyncIterator[uuid.UUID]:
    """A User's Event committed for real, so the worker's own connection sees it.
    Deleted afterwards, with the LLM calls the test made."""
    started = datetime.now(UTC) - timedelta(seconds=1)
    email = f"worker-{uuid4()}@example.com"
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        user = await register_user(
            session,
            UserCreate(email=email, password=GOOD_PASSWORD, timezone="Europe/Madrid"),
        )
        now = datetime.now(UTC)
        event = await create_event(
            session,
            user,
            EventCreate(
                type=EventType.INTERVIEW,
                target_language="es",
                event_day=(now + timedelta(days=12)).date(),
                level=Level.B1,
                daily_budget=30,
            ),
            now,
            job_queue=None,
        )
    try:
        yield event.id
    finally:
        async with AsyncSession(test_engine) as session:
            await delete_user_by_email(session, email)
            await session.execute(delete(LlmCall).where(LlmCall.called_at >= started))
            await session.commit()


async def test_the_worker_runs_an_events_job_with_generation_off(
    settings: Settings, pool: ArqRedis, committed_event: uuid.UUID, test_engine: AsyncEngine
) -> None:
    assert settings.anthropic_api_key is None
    await ArqJobQueue(pool).enqueue_event_content(committed_event)

    worker = await run_burst(worker_settings(settings), pool.default_queue_name)

    assert (worker.jobs_complete, worker.jobs_failed) == (1, 0)
    async with AsyncSession(test_engine) as session:
        outcomes = set(await session.scalars(select(LlmCall.outcome)))
    assert outcomes == {LlmOutcome.SKIPPED_NO_KEY}
