"""The per-Event content job: it tops each of the Event's Listen Dialogue pools up to
three through the content generator, records every attempt, and never touches the
schedule. Called directly, with a fake generator, the test database and real Redis."""

import uuid
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.listen import ListenDialogue, ListenSource
from app.models.llm_call import ContentKind, LlmCall, LlmOutcome
from app.services.catalog import Scenario
from app.services.content_generation import key_lock_name
from app.services.content_generator import Generation, OffContentGenerator
from app.services.listen_content import ListenDialogueContent
from app.services.planner import Level
from app.workers.tasks import generate_event_content
from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import create_event
from tests.tasks import INTRODUCING_YOURSELF
from tests.unit.test_listen_dialogue_content import dialogue


class FakeGenerator:
    """Returns a valid Listen Dialogue for every call, or raises for the Scenarios in
    `failing`. Records each call's (language, Scenario slug, Level)."""

    def __init__(
        self, *, failing: set[str] | None = None, cost_usd: Decimal = Decimal("0.01")
    ) -> None:
        self.calls: list[tuple[str, str, Level]] = []
        self.failing = failing or set()
        self.cost_usd = cost_usd

    async def listen_dialogue(
        self, language: str, scenario: Scenario, level: Level
    ) -> Generation[ListenDialogueContent]:
        self.calls.append((language, scenario.slug, level))
        if scenario.slug in self.failing:
            raise RuntimeError("the LLM said no")
        return Generation(
            content=ListenDialogueContent.model_validate(dialogue()),
            model="fake-model",
            input_tokens=100,
            output_tokens=200,
            cost_usd=self.cost_usd,
        )


@pytest.fixture
async def redis(settings: Settings) -> AsyncIterator[Redis]:
    client = Redis.from_url(settings.redis_url.get_secret_value())
    yield client
    await client.aclose()


@pytest.fixture
def ctx(settings: Settings, db_session: AsyncSession, redis: Redis, clock: Clock) -> dict[str, Any]:
    """A worker context like the real one's, on this test's rolled-back session."""

    @asynccontextmanager
    async def session_factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return {
        "settings": settings,
        "session_factory": session_factory,
        "redis": redis,
        "generator": FakeGenerator(),
        "now": lambda: clock.now,
    }


async def new_event(client: AsyncClient, user: RegisteredUser) -> str:
    """The default Event: an interview in Spanish at B1."""
    response = await create_event(client, user)
    assert response.status_code == 201, response.text
    event_id: str = response.json()["id"]
    return event_id


async def scenarios_of(client: AsyncClient, user: RegisteredUser, event_id: str) -> list[str]:
    plan = await client.get(f"/api/v1/events/{event_id}/plan", headers=user.headers)
    return [m["scenario_slug"] for m in plan.json()["milestones"]]


async def pool_sizes(session: AsyncSession) -> dict[tuple[str, str, Level | None], int]:
    rows = await session.execute(
        select(
            ListenDialogue.scenario_slug,
            ListenDialogue.language,
            ListenDialogue.level,
            func.count(),
        )
        .where(ListenDialogue.source == ListenSource.GENERATED)
        .group_by(ListenDialogue.scenario_slug, ListenDialogue.language, ListenDialogue.level)
    )
    return {(slug, language, level): count for slug, language, level, count in rows}


async def outcomes(session: AsyncSession) -> Counter[tuple[str, LlmOutcome]]:
    """How many LLM call rows there are for each (Scenario, outcome), since `FIXED_NOW`'s day."""
    rows = await session.execute(
        select(LlmCall.scenario_slug, LlmCall.outcome).where(LlmCall.called_at >= FIXED_NOW)
    )
    return Counter((slug, outcome) for slug, outcome in rows)


async def test_the_job_fills_each_scenarios_pool_to_three_at_the_events_level(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    event_id = await new_event(client, user)
    scenarios = await scenarios_of(client, user, event_id)

    await generate_event_content(ctx, event_id)

    assert await pool_sizes(db_session) == {(slug, "es", Level.B1): 3 for slug in scenarios}
    assert ctx["generator"].calls == [
        ("es", slug, Level.B1) for slug in scenarios for _ in range(3)
    ]
    assert INTRODUCING_YOURSELF in scenarios


async def test_every_attempt_is_recorded_with_what_it_used(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    event_id = await new_event(client, user)
    scenarios = await scenarios_of(client, user, event_id)

    await generate_event_content(ctx, event_id)

    calls = (await db_session.scalars(select(LlmCall))).all()
    assert len(calls) == 3 * len(scenarios)
    assert {
        (c.content_kind, c.language, c.level, c.model, c.input_tokens, c.output_tokens)
        for c in calls
    } == {("listen_dialogue", "es", Level.B1, "fake-model", 100, 200)}
    assert {c.cost_usd for c in calls} == {Decimal("0.01")}
    assert {c.outcome for c in calls} == {LlmOutcome.GENERATED}
    assert {c.called_at for c in calls} == {FIXED_NOW}
    assert all(c.latency_ms is not None and c.latency_ms >= 0 for c in calls)


async def test_running_the_job_again_makes_no_new_calls(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    event_id = await new_event(client, user)
    await generate_event_content(ctx, event_id)
    ctx["generator"] = FakeGenerator()

    await generate_event_content(ctx, event_id)

    assert ctx["generator"].calls == []


async def test_two_events_with_the_same_keys_share_their_content(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    await generate_event_content(ctx, await new_event(client, user))
    sizes = await pool_sizes(db_session)
    other = await register_and_log_in(client, email="bea@example.com")
    ctx["generator"] = FakeGenerator()

    await generate_event_content(ctx, await new_event(client, other))

    assert ctx["generator"].calls == []
    assert await pool_sizes(db_session) == sizes


async def test_a_partly_filled_pool_is_topped_up_to_three(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    db_session.add(
        ListenDialogue.from_content(
            ListenDialogueContent.model_validate(dialogue()),
            scenario_slug=INTRODUCING_YOURSELF,
            language="es",
            level=Level.B1,
            source=ListenSource.GENERATED,
            created_at=FIXED_NOW,
        )
    )
    await db_session.commit()
    event_id = await new_event(client, user)

    await generate_event_content(ctx, event_id)

    calls = ctx["generator"].calls
    assert calls.count(("es", INTRODUCING_YOURSELF, Level.B1)) == 2
    assert (await pool_sizes(db_session))[(INTRODUCING_YOURSELF, "es", Level.B1)] == 3


async def test_a_key_whose_generation_fails_gets_no_content_and_one_failed_call(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    ctx["generator"] = FakeGenerator(failing={INTRODUCING_YOURSELF})
    event_id = await new_event(client, user)
    scenarios = await scenarios_of(client, user, event_id)

    await generate_event_content(ctx, event_id)

    sizes = await pool_sizes(db_session)
    assert (INTRODUCING_YOURSELF, "es", Level.B1) not in sizes
    assert sizes == {
        (slug, "es", Level.B1): 3 for slug in scenarios if slug != INTRODUCING_YOURSELF
    }
    failed = {
        key: n for key, n in (await outcomes(db_session)).items() if key[0] == INTRODUCING_YOURSELF
    }
    assert failed == {(INTRODUCING_YOURSELF, LlmOutcome.FALLBACK_AFTER_FAILURE): 1}


async def test_calls_past_the_daily_budget_are_skipped_and_recorded(
    client: AsyncClient,
    user: RegisteredUser,
    ctx: dict[str, Any],
    db_session: AsyncSession,
    settings: Settings,
) -> None:
    # Yesterday's spending doesn't count against today's budget.
    db_session.add(
        LlmCall(
            content_kind="listen_dialogue",
            scenario_slug=INTRODUCING_YOURSELF,
            language="es",
            level=Level.B1,
            model="fake-model",
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal(50),
            latency_ms=1,
            outcome=LlmOutcome.GENERATED,
            called_at=FIXED_NOW - timedelta(days=1),
        )
    )
    await db_session.commit()
    ctx["settings"] = settings.model_copy(update={"llm_daily_budget_usd": Decimal(2)})
    ctx["generator"] = FakeGenerator(cost_usd=Decimal("0.75"))
    event_id = await new_event(client, user)
    scenarios = await scenarios_of(client, user, event_id)

    await generate_event_content(ctx, event_id)

    # 0, 0.75 and 1.50 are under the budget of 2; then 2.25 is spent.
    assert len(ctx["generator"].calls) == 3
    first, *rest = scenarios
    assert await outcomes(db_session) == Counter(
        {(first, LlmOutcome.GENERATED): 3} | {(slug, LlmOutcome.SKIPPED_CAP): 1 for slug in rest}
    )


async def test_a_key_another_job_is_filling_is_skipped(
    client: AsyncClient,
    user: RegisteredUser,
    ctx: dict[str, Any],
    db_session: AsyncSession,
    redis: Redis,
) -> None:
    event_id = await new_event(client, user)
    lock = redis.lock(
        key_lock_name(ContentKind.LISTEN_DIALOGUE, "es", INTRODUCING_YOURSELF, Level.B1),
        timeout=10,
    )
    assert await lock.acquire(blocking=False)
    try:
        await generate_event_content(ctx, event_id)
    finally:
        await lock.release()

    assert ("es", INTRODUCING_YOURSELF, Level.B1) not in ctx["generator"].calls
    assert (INTRODUCING_YOURSELF, "es", Level.B1) not in await pool_sizes(db_session)


async def test_the_job_never_changes_the_schedule(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any]
) -> None:
    event_id = await new_event(client, user)
    before = (await client.get(f"/api/v1/events/{event_id}/plan", headers=user.headers)).json()

    await generate_event_content(ctx, event_id)

    after = (await client.get(f"/api/v1/events/{event_id}/plan", headers=user.headers)).json()
    assert after == before


async def test_with_generation_off_every_key_is_recorded_as_skipped_once(
    client: AsyncClient, user: RegisteredUser, ctx: dict[str, Any], db_session: AsyncSession
) -> None:
    ctx["generator"] = OffContentGenerator()
    event_id = await new_event(client, user)
    scenarios = await scenarios_of(client, user, event_id)

    summary = await generate_event_content(ctx, event_id)

    assert await outcomes(db_session) == Counter(
        {(slug, LlmOutcome.SKIPPED_NO_KEY): 1 for slug in scenarios}
    )
    assert await pool_sizes(db_session) == {}
    assert summary == {"skipped_no_key": len(scenarios)}


async def test_an_unknown_event_does_nothing(ctx: dict[str, Any], db_session: AsyncSession) -> None:
    assert await generate_event_content(ctx, str(uuid.uuid4())) == {}
    assert ctx["generator"].calls == []
