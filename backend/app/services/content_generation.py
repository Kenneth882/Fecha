"""Filling an Event's shared content through the content generator, in the worker.

Postgres is the content store and the cache (ADR 0008): a (language, Scenario, Level)
key whose pool is full is skipped, so running this again for the same Event, or for
another Event with the same keys, makes no new calls. Redis only holds a short lock per
key, so two jobs never fill the same key at once. It never changes an Event's
Milestones or Tasks (ADR 0004).
"""

import logging
import time
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis
from redis.exceptions import LockError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, Milestone, Plan
from app.models.listen import ListenDialogue, ListenSource
from app.models.llm_call import ContentKind, LlmCall, LlmOutcome
from app.services.catalog import stored_scenario
from app.services.content_generator import (
    ContentGenerator,
    GenerationFailedError,
    GenerationSkippedError,
)
from app.services.planner import Level

logger = logging.getLogger(__name__)

# How many generated Listen Dialogues each key gets.
LISTEN_POOL_SIZE = 3
# Long enough to fill one key's pool, short enough that a crashed worker's lock soon
# lets another job try.
KEY_LOCK_SECONDS = 300


def key_lock_name(kind: ContentKind, language: str, scenario_slug: str, level: Level) -> str:
    """The Redis lock held while one job fills a (language, Scenario, Level) key."""
    return f"content-lock:{kind}:{language}:{scenario_slug}:{level}"


async def fill_event_content(
    session: AsyncSession,
    redis: Redis,
    generator: ContentGenerator,
    event_id: uuid.UUID,
    *,
    daily_budget_usd: Decimal,
    now: Callable[[], datetime],
) -> Counter[LlmOutcome]:
    """Top up the Listen Dialogue pool of each Scenario in the Event's Current Plan, at
    the Event's language and Level, and return how the attempts ended.

    Each attempt is recorded as an LLM call, and each generated dialogue is committed
    with its call. A key stops filling at its first skipped or failed attempt: what it
    generated before stays, and a later run tops the pool up. Before each call, the day's
    (UTC) total cost is checked against `daily_budget_usd`. A key another job is
    filling (its lock is held) is skipped: that job fills it, and if it fails, the next
    run for any Event with the key tries again. An unknown Event does nothing.
    """
    outcomes: Counter[LlmOutcome] = Counter()
    event = await session.get(Event, event_id)
    if event is None:
        logger.warning("no such Event to generate content for", extra={"event_id": str(event_id)})
        return outcomes
    for slug in await _current_scenarios(session, event):
        lock = redis.lock(
            key_lock_name(ContentKind.LISTEN_DIALOGUE, event.target_language, slug, event.level),
            timeout=KEY_LOCK_SECONDS,
            blocking=False,
        )
        if not await lock.acquire():
            logger.info("another job is filling this key", extra={"scenario": slug})
            continue
        try:
            await _fill_listen_pool(
                session, generator, event, slug, outcomes, daily_budget_usd, now
            )
        finally:
            try:
                await lock.release()
            except LockError:
                logger.warning("a key's lock expired while it was filled", extra={"scenario": slug})
    return outcomes


async def _current_scenarios(session: AsyncSession, event: Event) -> list[str]:
    """The Scenario slugs of the Event's Current Plan's Milestones, in order."""
    current = select(func.max(Plan.version)).where(Plan.event_id == event.id).scalar_subquery()
    rows = await session.scalars(
        select(Milestone.scenario_slug)
        .join(Plan, Milestone.plan_id == Plan.id)
        .where(Plan.event_id == event.id, Plan.version == current)
        .order_by(Milestone.position)
    )
    return list(dict.fromkeys(rows))


async def _fill_listen_pool(
    session: AsyncSession,
    generator: ContentGenerator,
    event: Event,
    slug: str,
    outcomes: Counter[LlmOutcome],
    daily_budget_usd: Decimal,
    now: Callable[[], datetime],
) -> None:
    language, level = event.target_language, event.level
    have = await session.scalar(
        select(func.count()).where(ListenDialogue.live_generated(slug, language, level))
    )
    scenario = stored_scenario(slug)
    for _ in range(LISTEN_POOL_SIZE - (have or 0)):
        call = LlmCall(
            content_kind=ContentKind.LISTEN_DIALOGUE,
            scenario_slug=slug,
            language=language,
            level=level,
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal(0),
        )
        if await _spent_today(session, now()) >= daily_budget_usd:
            await _record(session, call, LlmOutcome.SKIPPED_CAP, now(), outcomes)
            return
        started = time.perf_counter()
        try:
            generation = await generator.listen_dialogue(language, scenario, level)
        except GenerationSkippedError:
            await _record(session, call, LlmOutcome.SKIPPED_NO_KEY, now(), outcomes)
            return
        except Exception as exc:
            call.latency_ms = _elapsed_ms(started)
            if isinstance(exc, GenerationFailedError):
                _set_usage(call, exc.model, exc.input_tokens, exc.output_tokens, exc.cost_usd)
            logger.warning(
                "content generation failed; Users keep the fallback",
                exc_info=True,
                extra={"scenario": slug, "language": language, "level": str(level)},
            )
            await _record(session, call, LlmOutcome.FALLBACK_AFTER_FAILURE, now(), outcomes)
            return
        call.latency_ms = _elapsed_ms(started)
        _set_usage(
            call,
            generation.model,
            generation.input_tokens,
            generation.output_tokens,
            generation.cost_usd,
        )
        session.add(
            ListenDialogue.from_content(
                generation.content,
                scenario_slug=slug,
                language=language,
                level=level,
                source=ListenSource.GENERATED,
                created_at=now(),
            )
        )
        await _record(session, call, LlmOutcome.GENERATED, now(), outcomes)


async def _spent_today(session: AsyncSession, now: datetime) -> Decimal:
    """What the LLM calls since the start of `now`'s UTC day have cost."""
    since = datetime.combine(now.astimezone(UTC).date(), datetime.min.time(), tzinfo=UTC)
    total = await session.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(LlmCall.called_at >= since)
    )
    return Decimal(total or 0)


def _set_usage(
    call: LlmCall,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
) -> None:
    call.model = model
    call.input_tokens = input_tokens
    call.output_tokens = output_tokens
    call.cost_usd = cost_usd


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


async def _record(
    session: AsyncSession,
    call: LlmCall,
    outcome: LlmOutcome,
    at: datetime,
    outcomes: Counter[LlmOutcome],
) -> None:
    """Commit the call's row, with any content added alongside it."""
    call.outcome = outcome
    call.called_at = at
    session.add(call)
    await session.commit()
    outcomes[outcome] += 1
