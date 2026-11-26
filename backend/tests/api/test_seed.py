from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.seed import SeedVocabMissingError, seed_demo
from app.services.seed_vocab import load_seed_vocab, read_seed_vocab
from tests.conftest import Clock
from tests.demo import load_seed_content, log_in_as_demo
from tests.events import EVENTS
from tests.reviews import due
from tests.tasks import TASKS, tasks_today


async def demo_events(client: AsyncClient, settings: Settings) -> list[Any]:
    """The demo User's Events, as they see them after logging in with the demo
    credentials from settings."""
    headers = (await log_in_as_demo(client, settings)).headers
    response = await client.get(EVENTS, headers=headers)
    assert response.status_code == 200, response.text
    events: list[Any] = response.json()
    for event in events:
        plan = await client.get(f"{EVENTS}/{event['id']}/plan", headers=headers)
        assert plan.status_code == 200, plan.text
        event["plan"] = plan.json()
    return events


async def test_the_demo_user_can_log_in_and_sees_a_spanish_interview_12_days_out(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_content(db_session, clock.now)
    # The clock reads 13:00 on 2026-11-10 in Madrid, the demo User's timezone.
    await seed_demo(db_session, settings, clock.now)

    [event] = await demo_events(client, settings)

    assert (event["type"], event["target_language"]) == ("interview", "es")
    assert (event["event_day"], event["state"], event["days_until_event_day"]) == (
        "2026-11-22",
        "active",
        12,
    )
    assert event["plan"]["version"] == 1
    assert event["plan"]["milestones"]


async def test_re_seeding_on_a_later_day_leaves_one_fresh_event_12_days_out(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_content(db_session, clock.now)
    await seed_demo(db_session, settings, clock.now)
    # Three days later, the 2026-11-22 Event would be only 9 days out.
    clock.now = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
    await seed_demo(db_session, settings, clock.now)

    [event] = await demo_events(client, settings)

    assert (event["event_day"], event["state"], event["days_until_event_day"]) == (
        "2026-11-25",
        "active",
        12,
    )
    assert event["plan"]["version"] == 1


async def test_seeding_twice_leaves_the_demo_user_on_day_4_of_15_with_reviews_due(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_content(db_session, clock.now)
    await seed_demo(db_session, settings, clock.now)
    await seed_demo(db_session, settings, clock.now)

    demo = await log_in_as_demo(client, settings)
    [event] = (await client.get(EVENTS, headers=demo.headers)).json()
    today = (await client.get(f"{EVENTS}/{event['id']}/today", headers=demo.headers)).json()
    queue = await due(client, demo, event["id"])

    assert (today["today"], today["plan_day"], today["plan_days"]) == ("2026-11-10", 4, 15)
    assert (event["event_day"], today["days_until_event_day"]) == ("2026-11-22", 12)
    # One Review in 10 is Again. A first Review always comes back the next day, so due
    # today: Day 3's 6 new items, Day 2's 12 (first reviewed on Day 3), and two Day 1
    # items, Again on Day 2 (Review 10) and on Day 3 (Review 20).
    assert queue["count"] == 6 + 12 + 2
    # Today's Tasks are still to do.
    assert {task["status"] for task in today["tasks"]} == {"pending"}


async def test_the_demo_users_first_three_days_have_their_vocab_tasks_done(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_content(db_session, clock.now)
    await seed_demo(db_session, settings, clock.now)

    [event] = await demo_events(client, settings)
    earlier = {
        (day["date"], task["kind"], task["status"])
        for milestone in event["plan"]["milestones"]
        for day in milestone["days"]
        if day["date"] < "2026-11-10"
        for task in day["tasks"]
    }

    assert {date for date, _, _ in earlier} == {"2026-11-07", "2026-11-08", "2026-11-09"}
    assert {(kind, status) for _, kind, status in earlier} == {
        ("vocab", "completed"),
        ("listen", "missed"),
        ("speak", "missed"),
    }


async def test_seeding_without_the_seed_vocabulary_says_to_load_it(
    db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    with pytest.raises(SeedVocabMissingError, match="load_seed_vocab"):
        await seed_demo(db_session, settings, clock.now)


async def test_the_demo_users_listen_task_today_is_playable_on_the_fallback_dialogue(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_content(db_session, clock.now)
    await seed_demo(db_session, settings, clock.now)
    demo = await log_in_as_demo(client, settings)
    [event] = (await client.get(EVENTS, headers=demo.headers)).json()
    [listen, *_] = [
        t for t in await tasks_today(client, demo, event["id"]) if t["kind"] == "listen"
    ]

    opened = await client.get(f"{TASKS}/{listen['id']}/listen", headers=demo.headers)
    for question in (1, 2, 3):
        answered = await client.post(
            f"{TASKS}/{listen['id']}/answers",
            json={"question": question, "choice": 1},
            headers=demo.headers,
        )
        assert answered.status_code == 200, answered.text

    assert (opened.json()["answerable"], len(opened.json()["questions"])) == (True, 3)
    assert answered.json()["status"] == "completed"


async def test_seeding_without_the_fallback_listen_dialogues_says_to_load_them(
    db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_vocab(db_session, read_seed_vocab(), clock.now)

    with pytest.raises(SeedVocabMissingError, match="load_seed_vocab"):
        await seed_demo(db_session, settings, clock.now)
