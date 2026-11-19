"""End to end: the demo Plan from the seeded Day 4 to the Event Day 12 days later, with
every Vocab Task completed and the Review Queue cleared each day. Every Introduced Vocab
Item gets a Review in the Final Window, and those Reviews fit the Final Window's Review
allowance (ADR 0006)."""

from collections import Counter
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.review import Review, ReviewState
from app.seed import DEMO_DAYS_OUT, seed_demo
from app.services.planner import vocab_cap
from app.services.seed_vocab import load_seed_vocab, read_seed_vocab
from tests.auth import RegisteredUser
from tests.conftest import FIXED_NOW, Clock
from tests.demo import log_in_as_demo
from tests.events import EVENTS
from tests.reviews import due, grade
from tests.tasks import TASKS, tasks_today

# A mix of the four buttons, so some items are forgotten and come back the next day.
GRADES = ["good", "again", "good", "easy", "hard", "good", "good"]


async def complete_vocab_tasks(client: AsyncClient, demo: RegisteredUser, event_id: str) -> None:
    for task in await tasks_today(client, demo, event_id):
        if task["kind"] == "vocab":
            completed = await client.post(f"{TASKS}/{task['id']}/complete", headers=demo.headers)
            assert completed.status_code == 200, completed.text


async def clear_queue(
    client: AsyncClient, demo: RegisteredUser, event_id: str, graded: int
) -> list[dict[str, Any]]:
    """Grade every item in today's Review Queue, cycling through GRADES from `graded`
    Reviews in. Returns the queue as it was."""
    queue = await due(client, demo, event_id)
    for n, item in enumerate(queue["items"], start=graded):
        response = await grade(
            client, demo, event_id, item["vocab_item_id"], GRADES[n % len(GRADES)]
        )
        assert response.status_code == 200, response.text
    assert (await due(client, demo, event_id))["count"] == 0
    items: list[dict[str, Any]] = queue["items"]
    return items


async def test_clearing_the_queue_daily_reviews_every_item_in_the_final_window_within_budget(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await load_seed_vocab(db_session, read_seed_vocab(), FIXED_NOW)
    event = await seed_demo(db_session, settings, FIXED_NOW)
    demo = await log_in_as_demo(client, settings)
    event_id = str(event.id)
    first_day = date(2026, 11, 10)
    final_window = [event.event_day - timedelta(days=2), event.event_day - timedelta(days=1)]

    due_per_day: Counter[date] = Counter()
    graded = 0
    for n in range(DEMO_DAYS_OUT):
        clock.now = FIXED_NOW + timedelta(days=n)
        today = first_day + timedelta(days=n)
        await complete_vocab_tasks(client, demo, event_id)
        cleared = await clear_queue(client, demo, event_id, graded)
        due_per_day[today] = len(cleared)
        graded += len(cleared)

    introduced = set(
        await db_session.scalars(
            select(ReviewState.vocab_item_id).where(ReviewState.event_id == event.id)
        )
    )
    reviewed_in_final_window = set(
        await db_session.scalars(
            select(Review.vocab_item_id).where(
                Review.event_id == event.id, Review.plan_day.in_(final_window)
            )
        )
    )
    assert introduced, "the demo Plan introduces Vocab Items"
    assert reviewed_in_final_window == introduced
    # The combined Review allowance of the two days, in Reviews: `vocab_cap` is that
    # allowance at about 8 seconds a Review. Day 1 alone may go over (ADR 0006).
    assert sum(due_per_day[day] for day in final_window) <= vocab_cap(event.daily_budget)

    clock.now = FIXED_NOW + timedelta(days=DEMO_DAYS_OUT)
    assert (await due(client, demo, event_id))["count"] == 0
    on_the_day = await client.get(f"{EVENTS}/{event_id}/today", headers=demo.headers)
    assert on_the_day.json()["state"] == "event_day"
