"""Opening and completing a Vocab Task: its batch is fixed on first open, and completing
it introduces the batch's Vocab Items."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import ReviewState
from app.models.vocab import VocabItem, VocabSource
from app.services.planner import Level
from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import Clock
from tests.events import EVENTS, abandon, create_event

TASKS = "/api/v1/tasks"
# Plan Day 1 of the default Event (see test_today.py): two 6-item Vocab Tasks, then two
# Listen Tasks, all for this Scenario.
INTRODUCING_YOURSELF = "interview.introducing_yourself"
WALKING_THROUGH_YOUR_EXPERIENCE = "interview.walking_through_your_experience"


async def add_items(
    session: AsyncSession, scenario_slug: str, count: int, *, prefix: str = ""
) -> list[VocabItem]:
    """`count` Spanish seed Vocab Items for the Scenario, at positions 1..count,
    phrased "frase {prefix}{n}"."""
    items = [
        VocabItem(
            scenario_slug=scenario_slug,
            language="es",
            level=None,
            item_key=f"item_{prefix}{n}",
            phrase=f"frase {prefix}{n}",
            translation=f"phrase {prefix}{n}",
            position=n,
            source=VocabSource.SEED,
        )
        for n in range(1, count + 1)
    ]
    session.add_all(items)
    await session.commit()
    return items


async def todays_tasks(client: AsyncClient, user: RegisteredUser) -> list[dict[str, Any]]:
    event = (await create_event(client, user)).json()
    today = await client.get(f"{EVENTS}/{event['id']}/today", headers=user.headers)
    tasks: list[dict[str, Any]] = today.json()["tasks"]
    return tasks


async def open_vocab(client: AsyncClient, user: RegisteredUser, task_id: str) -> Any:
    response = await client.get(f"{TASKS}/{task_id}/vocab", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


def phrases(batch: dict[str, Any]) -> list[str]:
    return [item["phrase"] for item in batch["items"]]


def without_request_id(body: dict[str, Any]) -> dict[str, Any]:
    return {"error": {k: v for k, v in body["error"].items() if k != "request_id"}}


async def test_opening_a_vocab_task_shows_the_scenarios_first_items_up_to_its_batch_size(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    items = await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, _, _, _ = await todays_tasks(client, user)

    batch = await open_vocab(client, user, first["id"])

    assert batch == {
        "task_id": first["id"],
        "items": [
            {"id": str(item.id), "phrase": item.phrase, "translation": item.translation}
            for item in items[:6]
        ],
    }


async def test_reopening_returns_the_same_batch_even_after_the_scenario_changes(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    items = await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, _, _, _ = await todays_tasks(client, user)
    opened = await open_vocab(client, user, first["id"])
    # An item in the batch is retired and new items take the first positions.
    items[0].retired_at = clock.now
    await add_items(db_session, INTRODUCING_YOURSELF, 3, prefix="new_")

    assert await open_vocab(client, user, first["id"]) == opened


async def test_the_days_second_vocab_task_gets_the_next_items_not_the_same_ones(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, second, _, _ = await todays_tasks(client, user)

    # Opened in reverse order, before either is completed.
    second_batch = await open_vocab(client, user, second["id"])
    first_batch = await open_vocab(client, user, first["id"])

    assert phrases(second_batch) == [f"frase {n}" for n in range(1, 7)]
    assert phrases(first_batch) == [f"frase {n}" for n in range(7, 13)]


async def test_a_batch_skips_items_made_for_another_level(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    items = await add_items(db_session, INTRODUCING_YOURSELF, 8)
    items[0].level = Level.A1  # the Event is B1
    items[1].level = Level.B1
    first, _, _, _ = await todays_tasks(client, user)

    batch = await open_vocab(client, user, first["id"])

    assert phrases(batch) == [f"frase {n}" for n in range(2, 8)]


async def test_opening_a_listen_task_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    _, _, listen, _ = await todays_tasks(client, user)

    response = await client.get(f"{TASKS}/{listen['id']}/vocab", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_a_vocab_task"


async def complete(client: AsyncClient, user: RegisteredUser, task_id: str) -> Any:
    response = await client.post(f"{TASKS}/{task_id}/complete", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


async def review_states(session: AsyncSession) -> list[tuple[str, str, str | None]]:
    """(phrase, introduced_on, due_on) of every Review State, by phrase."""
    rows = await session.execute(
        select(VocabItem.phrase, ReviewState.introduced_on, ReviewState.due_on)
        .join(ReviewState, ReviewState.vocab_item_id == VocabItem.id)
        .order_by(VocabItem.position)
    )
    return [(p, str(i), str(d) if d else None) for p, i, d in rows]


async def test_completing_a_vocab_task_introduces_its_batch_first_due_the_next_day(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, _, _, _ = await todays_tasks(client, user)

    completion = await complete(client, user, first["id"])

    assert completion == {"task_id": first["id"], "status": "completed", "items_introduced": 6}
    assert await review_states(db_session) == [
        (f"frase {n}", "2026-11-10", "2026-11-11") for n in range(1, 7)
    ]
    # Completing fixed the batch, and opening it now shows the same items.
    assert phrases(await open_vocab(client, user, first["id"])) == [
        f"frase {n}" for n in range(1, 7)
    ]


async def test_completing_an_opened_task_introduces_the_batch_it_showed(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, second, _, _ = await todays_tasks(client, user)
    await open_vocab(client, user, first["id"])
    shown = await open_vocab(client, user, second["id"])

    await complete(client, user, second["id"])

    assert [phrase for phrase, _, _ in await review_states(db_session)] == phrases(shown)


async def test_completing_again_changes_nothing_and_answers_the_same(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, _, _, _ = await todays_tasks(client, user)
    completed = await complete(client, user, first["id"])
    states = await review_states(db_session)

    clock.now = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)
    assert await complete(client, user, first["id"]) == completed
    assert await review_states(db_session) == states


async def test_a_completed_task_shows_as_completed_in_today(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    event = (await create_event(client, user)).json()
    today_url = f"{EVENTS}/{event['id']}/today"
    first = (await client.get(today_url, headers=user.headers)).json()["tasks"][0]

    await complete(client, user, first["id"])

    tasks = (await client.get(today_url, headers=user.headers)).json()["tasks"]
    assert [t["status"] for t in tasks] == ["completed", "pending", "pending", "pending"]


async def test_a_scenario_that_runs_out_gives_a_short_batch_then_an_empty_one(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 8)
    first, second, _, _ = await todays_tasks(client, user)
    await complete(client, user, first["id"])

    short = await complete(client, user, second["id"])

    assert short["items_introduced"] == 2
    assert phrases(await open_vocab(client, user, second["id"])) == ["frase 7", "frase 8"]


async def test_a_vocab_task_with_no_items_left_still_completes_and_its_empty_batch_stays(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    first, _, _, _ = await todays_tasks(client, user)
    assert (await open_vocab(client, user, first["id"]))["items"] == []
    # Items arriving later don't refill a batch that was fixed empty.
    await add_items(db_session, INTRODUCING_YOURSELF, 20)

    completion = await complete(client, user, first["id"])

    assert (completion["status"], completion["items_introduced"]) == ("completed", 0)
    assert await review_states(db_session) == []


async def test_completing_a_missed_task_is_a_409_and_introduces_nothing(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, _, _, _ = await todays_tasks(client, user)
    await open_vocab(client, user, first["id"])
    clock.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)

    response = await client.post(f"{TASKS}/{first['id']}/complete", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_missed"
    assert await review_states(db_session) == []


async def test_completing_a_listen_task_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    _, _, listen, _ = await todays_tasks(client, user)

    response = await client.post(f"{TASKS}/{listen['id']}/complete", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_a_vocab_task"


async def test_completing_a_speak_task_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    await todays_tasks(client, user)
    clock.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    [event] = (await client.get(EVENTS, headers=user.headers)).json()
    today = (await client.get(f"{EVENTS}/{event['id']}/today", headers=user.headers)).json()
    [speak] = [t for t in today["tasks"] if t["kind"] == "speak"]

    response = await client.post(f"{TASKS}/{speak['id']}/complete", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_a_vocab_task"


async def test_completing_a_task_of_a_past_event_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_items(db_session, INTRODUCING_YOURSELF, 20)
    first, _, _, _ = await todays_tasks(client, user)
    [event] = (await client.get(EVENTS, headers=user.headers)).json()
    assert (await abandon(client, user, event["id"])).status_code == 200

    response = await client.post(f"{TASKS}/{first['id']}/complete", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_already_past"
    assert await review_states(db_session) == []


async def test_a_missed_tasks_batch_goes_back_to_its_scenarios_later_vocab_tasks(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    # This Scenario has two Vocab Tasks on Plan Day 2 (2026-11-11) and one on Plan Day 3.
    await add_items(db_session, WALKING_THROUGH_YOUR_EXPERIENCE, 30)
    event = (await create_event(client, user)).json()
    clock.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    first, second, _, _ = (
        await client.get(f"{EVENTS}/{event['id']}/today", headers=user.headers)
    ).json()["tasks"]
    assert phrases(await open_vocab(client, user, first["id"]))[0] == "frase 1"
    await complete(client, user, second["id"])  # frase 7 to frase 12
    clock.now = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    [day_3_vocab] = [
        t
        for t in (await client.get(f"{EVENTS}/{event['id']}/today", headers=user.headers)).json()[
            "tasks"
        ]
        if t["kind"] == "vocab"
    ]

    batch = await open_vocab(client, user, day_3_vocab["id"])

    # The first Task is now Missed, so its items come before frase 13 again.
    assert phrases(batch) == [f"frase {n}" for n in range(1, 7)]


@pytest.mark.parametrize("action", ["open", "complete"])
async def test_another_users_task_is_a_404_identical_to_an_unknown_id(
    client: AsyncClient, user: RegisteredUser, clock: Clock, action: str
) -> None:
    other = await register_and_log_in(client, email="other@example.com")
    theirs, _, _, _ = await todays_tasks(client, other)

    async def send(task_id: str) -> Any:
        if action == "open":
            return await client.get(f"{TASKS}/{task_id}/vocab", headers=user.headers)
        return await client.post(f"{TASKS}/{task_id}/complete", headers=user.headers)

    for_theirs = await send(theirs["id"])
    for_unknown = await send(str(uuid.uuid4()))

    assert for_theirs.status_code == for_unknown.status_code == 404
    assert without_request_id(for_theirs.json()) == without_request_id(for_unknown.json())
    assert for_theirs.json()["error"]["code"] == "task_not_found"
