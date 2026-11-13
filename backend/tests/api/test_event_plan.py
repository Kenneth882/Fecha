import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Milestone, Plan, Task
from app.services.planner import TaskKind
from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import Clock
from tests.events import EVENTS, create_event


async def get_plan(client: AsyncClient, user: RegisteredUser, event_id: str) -> Any:
    response = await client.get(f"{EVENTS}/{event_id}/plan", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


def without_ids(milestone: dict[str, Any]) -> dict[str, Any]:
    days = [
        {**day, "tasks": [{k: v for k, v in t.items() if k != "id"} for t in day["tasks"]]}
        for day in milestone["days"]
    ]
    return {**milestone, "days": days}


async def test_a_new_events_plan_lists_its_milestones_and_tasks_in_order(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    # An interview at B1, 30 minutes a day, 12 days out from 2026-11-10 in Madrid.
    event = (await create_event(client, user)).json()

    plan = await get_plan(client, user, event["id"])

    assert plan["version"] == 1
    assert [m["scenario_slug"] for m in plan["milestones"]] == [
        "interview.introducing_yourself",
        "interview.walking_through_your_experience",
        "interview.why_this_role",
        "interview.describing_a_challenge",
    ]
    assert [m["position"] for m in plan["milestones"]] == [1, 2, 3, 4]
    # The first Milestone in full: title and difficulty come from the Scenario Catalog,
    # its Tasks are grouped by Plan Day in date order, and nothing is due before today.
    assert without_ids(plan["milestones"][0]) == {
        "scenario_slug": "interview.introducing_yourself",
        "title": "Introducing yourself",
        "difficulty": 1,
        "position": 1,
        "target_date": "2026-11-10",
        "days": [
            {
                "date": "2026-11-10",
                "tasks": [
                    {"kind": "vocab", "position": 1, "estimated_minutes": 6, "status": "pending"},
                    {"kind": "vocab", "position": 2, "estimated_minutes": 6, "status": "pending"},
                    {"kind": "listen", "position": 3, "estimated_minutes": 5, "status": "pending"},
                    {"kind": "listen", "position": 4, "estimated_minutes": 5, "status": "pending"},
                ],
            },
            {
                "date": "2026-11-11",
                "tasks": [
                    {"kind": "speak", "position": 4, "estimated_minutes": 5, "status": "pending"}
                ],
            },
            {
                "date": "2026-11-12",
                "tasks": [
                    {"kind": "listen", "position": 4, "estimated_minutes": 5, "status": "pending"}
                ],
            },
            {
                "date": "2026-11-20",
                "tasks": [
                    {"kind": "listen", "position": 4, "estimated_minutes": 5, "status": "pending"}
                ],
            },
            {
                "date": "2026-11-21",
                "tasks": [
                    {"kind": "listen", "position": 4, "estimated_minutes": 5, "status": "pending"}
                ],
            },
        ],
    }
    task_ids = [
        task["id"] for m in plan["milestones"] for day in m["days"] for task in day["tasks"]
    ]
    assert len(set(task_ids)) == len(task_ids)
    for task_id in task_ids:
        uuid.UUID(task_id)


def statuses_by_date(plan: Any) -> dict[str, set[str]]:
    by_date: dict[str, set[str]] = {}
    for milestone in plan["milestones"]:
        for day in milestone["days"]:
            by_date.setdefault(day["date"], set()).update(t["status"] for t in day["tasks"])
    return by_date


# Madrid is UTC+1 in November, so its local midnight is 23:00 UTC the day before.
@pytest.mark.parametrize(
    ("now", "today_in_madrid"),
    [
        # The last minute of 2026-11-11 in Madrid: only 2026-11-10 has ended.
        (datetime(2026, 11, 11, 22, 59, tzinfo=UTC), "2026-11-11"),
        # The first minute of 2026-11-12 there: 2026-11-11 has ended too.
        (datetime(2026, 11, 11, 23, 0, tzinfo=UTC), "2026-11-12"),
        (datetime(2026, 11, 18, 12, 0, tzinfo=UTC), "2026-11-18"),
    ],
)
async def test_incomplete_tasks_turn_missed_once_their_plan_day_ends(
    client: AsyncClient, user: RegisteredUser, clock: Clock, now: datetime, today_in_madrid: str
) -> None:
    event = (await create_event(client, user)).json()
    clock.now = now

    by_date = statuses_by_date(await get_plan(client, user, event["id"]))

    assert by_date == {day: {"missed"} if day < today_in_madrid else {"pending"} for day in by_date}
    assert any(day < today_in_madrid for day in by_date)
    assert today_in_madrid in by_date


async def test_another_users_plan_returns_404(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    other = await register_and_log_in(client, email="other@example.com")
    theirs = (await create_event(client, other)).json()

    for_theirs = await client.get(f"{EVENTS}/{theirs['id']}/plan", headers=user.headers)
    for_unknown = await client.get(f"{EVENTS}/{uuid.uuid4()}/plan", headers=user.headers)

    assert for_theirs.status_code == for_unknown.status_code == 404
    assert for_theirs.json()["error"]["code"] == "event_not_found"


async def test_only_the_current_plan_is_shown_not_a_superseded_one(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    event = (await create_event(client, user)).json()
    # Re-planning doesn't exist yet, so store a second version directly.
    db_session.add(
        Plan(
            event_id=uuid.UUID(event["id"]),
            version=2,
            generated_at=clock.now,
            milestones=[
                Milestone(
                    scenario_slug="interview.salary_negotiation",
                    position=1,
                    target_date=date(2026, 11, 21),
                    tasks=[
                        Task(
                            date=date(2026, 11, 21),
                            kind=TaskKind.SPEAK,
                            position=1,
                            estimated_minutes=10,
                        )
                    ],
                )
            ],
        )
    )
    await db_session.flush()

    plan = await get_plan(client, user, event["id"])

    assert plan["version"] == 2
    assert [m["scenario_slug"] for m in plan["milestones"]] == ["interview.salary_negotiation"]
    assert plan["milestones"][0]["title"] == "Salary negotiation"
    assert plan["milestones"][0]["difficulty"] == 3
