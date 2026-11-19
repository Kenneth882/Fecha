"""The Review Queue and grading: Introduced Vocab Items come due by spaced repetition,
and the User grades each one Again, Hard, Good or Easy."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import Clock
from tests.events import EVENTS, abandon, create_event
from tests.reviews import due, grade
from tests.tasks import (
    INTRODUCING_YOURSELF,
    TASKS,
    WALKING_THROUGH_YOUR_EXPERIENCE,
    add_items,
    tasks_today,
    without_request_id,
)

# Noon UTC (13:00 in Madrid) on the default Event's Plan Days 2 and 3.
DAY_2 = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
DAY_3 = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
EVENT_DAY = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


async def complete_first_vocab_task(
    client: AsyncClient, user: RegisteredUser, event_id: str
) -> list[dict[str, Any]]:
    """Complete today's first Vocab Task and return the batch it introduced."""
    first = next(t for t in await tasks_today(client, user, event_id) if t["kind"] == "vocab")
    batch = (await client.get(f"{TASKS}/{first['id']}/vocab", headers=user.headers)).json()
    completed = await client.post(f"{TASKS}/{first['id']}/complete", headers=user.headers)
    assert completed.status_code == 200, completed.text
    items: list[dict[str, Any]] = batch["items"]
    return items


async def event_with_first_task_done(
    client: AsyncClient, user: RegisteredUser, db_session: AsyncSession
) -> tuple[str, list[dict[str, Any]]]:
    """Create the default Event and complete Plan Day 1's first Vocab Task (6 items).

    Returns the Event's id and the introduced batch."""
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    event_id = (await create_event(client, user)).json()["id"]
    return event_id, await complete_first_vocab_task(client, user, event_id)


async def test_the_day_after_a_vocab_task_its_items_are_due(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    assert (await due(client, user, event_id)) == {"count": 0, "items": []}

    clock.now = DAY_2
    queue = await due(client, user, event_id)

    assert queue["count"] == 6
    assert queue["items"] == [
        {
            "vocab_item_id": item["id"],
            "phrase": item["phrase"],
            "translation": item["translation"],
            "scenario_title": "Introducing yourself",
            "due_on": "2026-11-11",
        }
        for item in batch
    ]


async def test_overdue_items_are_carried_forward_oldest_first(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, first_batch = await event_with_first_task_done(client, user, db_session)
    await add_items(db_session, WALKING_THROUGH_YOUR_EXPERIENCE, 20, prefix="w")
    clock.now = DAY_2
    second_batch = await complete_first_vocab_task(client, user, event_id)

    clock.now = DAY_3
    queue = await due(client, user, event_id)

    assert queue["count"] == 12
    assert [(i["vocab_item_id"], i["due_on"]) for i in queue["items"]] == [
        *((item["id"], "2026-11-11") for item in first_batch),
        *((item["id"], "2026-11-12") for item in second_batch),
    ]


async def reviews_of(db_session: AsyncSession, item_id: str) -> list[Review]:
    return list(
        await db_session.scalars(select(Review).where(Review.vocab_item_id == uuid.UUID(item_id)))
    )


async def test_a_grade_moves_the_item_on_and_appends_exactly_one_review(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    clock.now = DAY_2
    item_id = batch[0]["id"]

    response = await grade(client, user, event_id, item_id, "good")

    assert response.status_code == 200, response.text
    # A first Review passed: SM-2's first interval, 1 day.
    assert response.json() == {"vocab_item_id": item_id, "due_on": "2026-11-12"}
    queue = await due(client, user, event_id)
    assert item_id not in [i["vocab_item_id"] for i in queue["items"]]
    assert queue["count"] == 5
    [review] = await reviews_of(db_session, item_id)
    assert (review.plan_day, review.grade, review.reviewed_at) == (date(2026, 11, 11), 4, DAY_2)

    clock.now = DAY_3
    assert item_id in [i["vocab_item_id"] for i in (await due(client, user, event_id))["items"]]


async def test_a_second_grade_the_same_day_is_a_409_and_logs_nothing(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    clock.now = DAY_2
    item_id = batch[0]["id"]
    assert (await grade(client, user, event_id, item_id, "again")).status_code == 200

    response = await grade(client, user, event_id, item_id, "good")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "review_not_due"
    assert len(await reviews_of(db_session, item_id)) == 1


async def test_grading_an_item_before_it_is_due_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    # Introduced today, so first due tomorrow.
    event_id, batch = await event_with_first_task_done(client, user, db_session)

    response = await grade(client, user, event_id, batch[0]["id"], "good")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "review_not_due"
    assert await reviews_of(db_session, batch[0]["id"]) == []


async def test_on_the_event_day_the_queue_is_empty_and_grading_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    # Never reviewed, so overdue since Plan Day 2.
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    clock.now = EVENT_DAY

    assert (await due(client, user, event_id)) == {"count": 0, "items": []}
    response = await grade(client, user, event_id, batch[0]["id"], "good")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_day_reached"
    assert await reviews_of(db_session, batch[0]["id"]) == []


@pytest.mark.parametrize("when", ["abandoned", "after_the_event_day"])
async def test_for_a_past_event_the_queue_is_empty_and_grading_is_a_409(
    client: AsyncClient,
    user: RegisteredUser,
    clock: Clock,
    db_session: AsyncSession,
    when: str,
) -> None:
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    clock.now = DAY_3
    if when == "abandoned":
        assert (await abandon(client, user, event_id)).status_code == 200
    else:
        clock.now = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)

    assert (await due(client, user, event_id)) == {"count": 0, "items": []}
    response = await grade(client, user, event_id, batch[0]["id"], "good")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_already_past"
    assert await reviews_of(db_session, batch[0]["id"]) == []


async def test_grading_an_item_not_introduced_for_the_event_is_a_404(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, _ = await event_with_first_task_done(client, user, db_session)
    clock.now = DAY_2
    # In the Scenario, but its Vocab Task isn't completed.
    [not_introduced] = await add_items(db_session, INTRODUCING_YOURSELF, 1, prefix="x")

    for item_id in [str(not_introduced.id), str(uuid.uuid4())]:
        response = await grade(client, user, event_id, item_id, "good")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "vocab_item_not_introduced"


async def test_another_users_event_is_a_404_identical_to_an_unknown_id(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    clock.now = DAY_2
    other = await register_and_log_in(client, email="luis@example.com")

    for path in [f"{EVENTS}/{event_id}", f"{EVENTS}/{uuid.uuid4()}"]:
        queue = await client.get(f"{path}/reviews/due", headers=other.headers)
        graded = await client.post(
            f"{path}/reviews",
            json={"vocab_item_id": batch[0]["id"], "grade": "good"},
            headers=other.headers,
        )
        for response in [queue, graded]:
            assert response.status_code == 404
            assert without_request_id(response.json()) == {
                "error": {"code": "event_not_found", "message": "No such Event", "details": []}
            }
    assert await reviews_of(db_session, batch[0]["id"]) == []


async def test_an_unknown_grade_is_a_422(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event_id, batch = await event_with_first_task_done(client, user, db_session)
    clock.now = DAY_2

    response = await grade(client, user, event_id, batch[0]["id"], "perfect")

    assert response.status_code == 422
