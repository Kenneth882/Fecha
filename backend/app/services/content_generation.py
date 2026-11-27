"""Filling an Event's shared content through the content generator, in the worker.

Postgres is the content store and the cache (ADR 0008): a (language, Scenario, Level)
key that's already filled is skipped, so running this again for the same Event, or for
another Event with the same keys, makes no new calls. Redis only holds a short lock per
key, so two jobs never fill the same key at once. It never changes an Event's
Milestones or Tasks (ADR 0004).
"""

import hashlib
import logging
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis
from redis.exceptions import LockError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, Milestone, Plan
from app.models.listen import ListenDialogue, ListenSource
from app.models.llm_call import ContentKind, LlmCall, LlmOutcome
from app.models.vocab import GENERATED_KEY_PREFIX, VocabItem, VocabSource
from app.services.catalog import stored_scenario
from app.services.content_generator import (
    ContentGenerator,
    Generation,
    GenerationFailedError,
    GenerationSkippedError,
)
from app.services.planner import Level
from app.services.vocab_content import (
    GENERATED_POSITIONS_AFTER,
    VOCAB_ITEM_COUNT,
    new_items,
    phrase_key,
)

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
    """For each Scenario in the Event's Current Plan, at the Event's language and Level,
    top up the Listen Dialogue pool and add the Level's generated Vocab Items if it has
    none yet; return how the attempts ended.

    Each attempt is recorded as an LLM call, and what it generated is committed with its
    call. A key stops filling at its first skipped or failed attempt: what it generated
    before stays, and a later run tops it up. Before each call, the day's (UTC) total
    cost is checked against `daily_budget_usd`. A key another job is filling (its lock is
    held) is skipped: that job fills it, and if it fails, the next run for any Event with
    the key tries again. An unknown Event does nothing.
    """
    run = _Run(session, generator, Counter(), daily_budget_usd, now)
    event = await session.get(Event, event_id)
    if event is None:
        logger.warning("no such Event to generate content for", extra={"event_id": str(event_id)})
        return run.outcomes
    fills: tuple[tuple[ContentKind, _Fill], ...] = (
        (ContentKind.LISTEN_DIALOGUE, _fill_listen_pool),
        (ContentKind.VOCAB_ITEMS, _fill_vocab_items),
    )
    for slug in await _current_scenarios(session, event):
        for kind, fill in fills:
            lock = redis.lock(
                key_lock_name(kind, event.target_language, slug, event.level),
                timeout=KEY_LOCK_SECONDS,
                blocking=False,
            )
            if not await lock.acquire():
                logger.info(
                    "another job is filling this key", extra={"scenario": slug, "kind": str(kind)}
                )
                continue
            try:
                await fill(run, event, slug)
            finally:
                try:
                    await lock.release()
                except LockError:
                    logger.warning(
                        "a key's lock expired while it was filled",
                        extra={"scenario": slug, "kind": str(kind)},
                    )
    return run.outcomes


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


@dataclass
class _Run:
    """One job's generator, its session, and the outcomes of its attempts so far."""

    session: AsyncSession
    generator: ContentGenerator
    outcomes: Counter[LlmOutcome]
    daily_budget_usd: Decimal
    now: Callable[[], datetime]

    async def attempt[T](
        self,
        kind: ContentKind,
        event: Event,
        slug: str,
        generate: Callable[[], Awaitable[Generation[T]]],
    ) -> tuple[LlmCall, T] | None:
        """Make one call, unless the day's budget is spent.

        A skipped or failed call is recorded and committed here, and gives None. A
        successful one gives its call row, with what it used, and its content: the caller
        adds what it stores and then `record`s the call, so both commit together.
        """
        call = LlmCall(
            content_kind=kind,
            scenario_slug=slug,
            language=event.target_language,
            level=event.level,
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal(0),
        )
        if await _spent_today(self.session, self.now()) >= self.daily_budget_usd:
            await self.record(call, LlmOutcome.SKIPPED_CAP)
            return None
        started = time.perf_counter()
        try:
            generation = await generate()
        except GenerationSkippedError:
            await self.record(call, LlmOutcome.SKIPPED_NO_KEY)
            return None
        except Exception as exc:
            call.latency_ms = _elapsed_ms(started)
            if isinstance(exc, GenerationFailedError):
                _set_usage(call, exc.model, exc.input_tokens, exc.output_tokens, exc.cost_usd)
            logger.warning(
                "content generation failed; Users keep the fallback",
                exc_info=True,
                extra={
                    "kind": str(kind),
                    "scenario": slug,
                    "language": event.target_language,
                    "level": str(event.level),
                },
            )
            await self.record(call, LlmOutcome.FALLBACK_AFTER_FAILURE)
            return None
        call.latency_ms = _elapsed_ms(started)
        _set_usage(
            call,
            generation.model,
            generation.input_tokens,
            generation.output_tokens,
            generation.cost_usd,
        )
        return call, generation.content

    async def record(self, call: LlmCall, outcome: LlmOutcome) -> None:
        """Commit the call's row, with any content added alongside it."""
        call.outcome = outcome
        call.called_at = self.now()
        self.session.add(call)
        await self.session.commit()
        self.outcomes[outcome] += 1


type _Fill = Callable[[_Run, Event, str], Awaitable[None]]


async def _fill_listen_pool(run: _Run, event: Event, slug: str) -> None:
    language, level = event.target_language, event.level
    have = await run.session.scalar(
        select(func.count()).where(ListenDialogue.live_generated(slug, language, level))
    )
    scenario = stored_scenario(slug)
    for _ in range(LISTEN_POOL_SIZE - (have or 0)):
        attempted = await run.attempt(
            ContentKind.LISTEN_DIALOGUE,
            event,
            slug,
            lambda: run.generator.listen_dialogue(language, scenario, level),
        )
        if attempted is None:
            return
        call, content = attempted
        run.session.add(
            ListenDialogue.from_content(
                content,
                scenario_slug=slug,
                language=language,
                level=level,
                source=ListenSource.GENERATED,
                created_at=run.now(),
            )
        )
        await run.record(call, LlmOutcome.GENERATED)


async def _fill_vocab_items(run: _Run, event: Event, slug: str) -> None:
    """Add the key's generated Vocab Items, unless a call has generated them already.

    Done once per key: what that call gave is kept, even if every phrase repeated an
    existing one and nothing was added, and a bad item is retired by hand, never
    replaced. So running the job again never pays for another call.
    """
    language, level = event.target_language, event.level
    already = await run.session.scalar(
        select(func.count()).where(
            LlmCall.content_kind == ContentKind.VOCAB_ITEMS,
            LlmCall.scenario_slug == slug,
            LlmCall.language == language,
            LlmCall.level == level,
            LlmCall.outcome == LlmOutcome.GENERATED,
        )
    )
    if already:
        return
    rows = (
        await run.session.execute(
            select(VocabItem.phrase, VocabItem.position).where(
                VocabItem.scenario_slug == slug, VocabItem.language == language
            )
        )
    ).all()
    existing = [phrase for phrase, _ in rows]
    scenario = stored_scenario(slug)
    attempted = await run.attempt(
        ContentKind.VOCAB_ITEMS,
        event,
        slug,
        lambda: run.generator.vocab_items(language, scenario, level, VOCAB_ITEM_COUNT, existing),
    )
    if attempted is None:
        return
    call, content = attempted
    last = max([GENERATED_POSITIONS_AFTER, *(position for _, position in rows)])
    kept = new_items(content, existing)
    if len(kept) < len(content.items):
        logger.info(
            "dropped generated phrases that repeat an existing Vocab Item",
            extra={"scenario": slug, "dropped": len(content.items) - len(kept)},
        )
    run.session.add_all(
        VocabItem(
            scenario_slug=slug,
            language=language,
            level=level,
            item_key=_generated_key(level, item.phrase),
            phrase=item.phrase,
            translation=item.translation,
            position=last + n,
            source=VocabSource.GENERATED,
        )
        for n, item in enumerate(kept, start=1)
    )
    await run.record(call, LlmOutcome.GENERATED)


def _generated_key(level: Level, phrase: str) -> str:
    """A generated item's key: the prefix, its Level, and a hash of its phrase's key.

    The Level keeps keys distinct when two Levels' jobs, which hold different locks,
    happen to generate the same phrase at once.
    """
    digest = hashlib.sha256(phrase_key(phrase).encode()).hexdigest()[:16]
    return f"{GENERATED_KEY_PREFIX}{level.lower()}_{digest}"


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
