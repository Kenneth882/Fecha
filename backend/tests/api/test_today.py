import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import Clock
from tests.events import EVENTS, abandon, create_event


async def get_today(client: AsyncClient, user: RegisteredUser, event_id: str) -> Any:
    response = await client.get(f"{EVENTS}/{event_id}/today", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


def without_ids(today: dict[str, Any]) -> dict[str, Any]:
    return {**today, "tasks": [{k: v for k, v in t.items() if k != "id"} for t in today["tasks"]]}


async def test_on_the_creation_day_it_is_plan_day_1_with_that_days_tasks_in_order(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    # An interview at B1, 30 minutes a day, created 2026-11-10 in Madrid for 2026-11-22.
    event = (await create_event(client, user)).json()

    today = await get_today(client, user, event["id"])

    title = "Introducing yourself"
    assert without_ids(today) == {
        "today": "2026-11-10",
        "plan_day": 1,
        "plan_days": 12,
        "days_until_event_day": 12,
        "state": "active",
        "current_plan_version": 1,
        "tasks": [
            {"scenario_title": title, "kind": "vocab", "estimated_minutes": 6, "status": "pending"},
            {"scenario_title": title, "kind": "vocab", "estimated_minutes": 6, "status": "pending"},
            {
                "scenario_title": title,
                "kind": "listen",
                "estimated_minutes": 5,
                "status": "pending",
            },
            {
                "scenario_title": title,
                "kind": "listen",
                "estimated_minutes": 5,
                "status": "pending",
            },
        ],
    }


async def test_a_later_day_lists_that_days_tasks_across_milestones_in_order(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    event = (await create_event(client, user)).json()
    clock.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)

    today = await get_today(client, user, event["id"])

    assert (today["today"], today["plan_day"], today["plan_days"]) == ("2026-11-11", 2, 12)
    assert today["days_until_event_day"] == 11
    assert today["state"] == "active"
    assert [(t["scenario_title"], t["kind"], t["estimated_minutes"]) for t in today["tasks"]] == [
        ("Walking through your experience", "vocab", 6),
        ("Walking through your experience", "vocab", 6),
        ("Walking through your experience", "listen", 5),
        ("Introducing yourself", "speak", 5),
    ]
    assert {t["status"] for t in today["tasks"]} == {"pending"}


# Madrid is UTC+1 in November; the Event Day is 2026-11-22 there.
@pytest.mark.parametrize(
    ("now", "today_in_madrid", "state"),
    [
        (datetime(2026, 11, 22, 9, 0, tzinfo=UTC), "2026-11-22", "event_day"),
        (datetime(2026, 11, 23, 9, 0, tzinfo=UTC), "2026-11-23", "past"),
    ],
)
async def test_on_and_after_the_event_day_there_is_no_plan_day_and_no_tasks(
    client: AsyncClient,
    user: RegisteredUser,
    clock: Clock,
    now: datetime,
    today_in_madrid: str,
    state: str,
) -> None:
    event = (await create_event(client, user)).json()
    clock.now = now

    today = await get_today(client, user, event["id"])

    assert today == {
        "today": today_in_madrid,
        "plan_day": None,
        "plan_days": 12,
        "days_until_event_day": 0,
        "state": state,
        "current_plan_version": 1,
        "tasks": [],
    }


async def test_an_abandoned_event_is_past_with_no_tasks_even_mid_plan(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    event = (await create_event(client, user)).json()
    assert (await abandon(client, user, event["id"])).status_code == 200

    today = await get_today(client, user, event["id"])

    assert (today["state"], today["plan_day"], today["tasks"]) == ("past", None, [])
    assert today["days_until_event_day"] == 12


# Los Angeles is UTC-8 in November: 23:30 there on 2026-11-10 is 07:30 UTC on 2026-11-11.
CREATED_LATE_IN_LA = datetime(2026, 11, 11, 7, 30, tzinfo=UTC)


# Plan Day 1's Tasks are all "Introducing yourself"; Plan Day 2's start with
# "Walking through your experience" (see the tests above, in Madrid).
@pytest.mark.parametrize(
    ("now", "today_in_la", "plan_day", "first_title"),
    [
        # The creation moment, late at night: still Plan Day 1, with its own Tasks.
        (CREATED_LATE_IN_LA, "2026-11-10", 1, "Introducing yourself"),
        # The last minute of 2026-11-10 in Los Angeles.
        (datetime(2026, 11, 11, 7, 59, tzinfo=UTC), "2026-11-10", 1, "Introducing yourself"),
        # Local midnight: Plan Day 2 begins, though the UTC date hasn't changed.
        (
            datetime(2026, 11, 11, 8, 0, tzinfo=UTC),
            "2026-11-11",
            2,
            "Walking through your experience",
        ),
    ],
)
async def test_today_follows_the_users_timezone_across_local_midnight(
    client: AsyncClient,
    clock: Clock,
    now: datetime,
    today_in_la: str,
    plan_day: int,
    first_title: str,
) -> None:
    la_user = await register_and_log_in(client, timezone="America/Los_Angeles")
    clock.now = CREATED_LATE_IN_LA
    event = (await create_event(client, la_user)).json()
    clock.now = now

    today = await get_today(client, la_user, event["id"])

    assert (today["today"], today["plan_day"], today["plan_days"]) == (today_in_la, plan_day, 12)
    assert len(today["tasks"]) == 4
    assert today["tasks"][0]["scenario_title"] == first_title


async def test_another_users_event_returns_404(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    other = await register_and_log_in(client, email="other@example.com")
    theirs = (await create_event(client, other)).json()

    for_theirs = await client.get(f"{EVENTS}/{theirs['id']}/today", headers=user.headers)
    for_unknown = await client.get(f"{EVENTS}/{uuid.uuid4()}/today", headers=user.headers)

    assert for_theirs.status_code == for_unknown.status_code == 404
    assert for_theirs.json()["error"]["code"] == "event_not_found"
