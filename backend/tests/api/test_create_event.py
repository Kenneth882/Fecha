import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response

from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import create_event


async def test_creating_an_event_returns_201_with_its_detail_and_plan_version_1(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    response = await create_event(client, user)

    assert response.status_code == 201, response.text
    detail = response.json()
    uuid.UUID(detail["id"])
    assert datetime.fromisoformat(detail["created_at"]) == FIXED_NOW
    assert {k: v for k, v in detail.items() if k not in {"id", "created_at"}} == {
        "type": "interview",
        "target_language": "es",
        "event_day": "2026-11-22",
        "level": "B1",
        "daily_budget": 30,
        "goals": "A nursing role at a hospital",
        "abandoned_at": None,
        "state": "active",
        "days_until_event_day": 12,
        "current_plan_version": 1,
    }


@pytest.mark.parametrize("goals", [None, "x" * 500])
async def test_goals_are_optional_and_up_to_500_characters(
    client: AsyncClient, user: RegisteredUser, clock: Clock, goals: str | None
) -> None:
    response = await create_event(client, user, goals=goals)

    assert response.status_code == 201, response.text
    assert response.json()["goals"] == goals


def error_fields(response: Response) -> list[str | None]:
    return [detail["field"] for detail in response.json()["error"]["details"]]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_language", "fr"),
        ("target_language", "ES"),
        ("daily_budget", 20),
        ("daily_budget", 60),
        ("level", "C2"),
        ("level", "b1"),
        ("type", "wedding"),
        ("goals", "x" * 501),
    ],
)
async def test_a_field_outside_what_cramplan_supports_returns_422_naming_it(
    client: AsyncClient, user: RegisteredUser, clock: Clock, field: str, value: object
) -> None:
    response = await create_event(client, user, **{field: value})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert error_fields(response) == [field]


# The `user` fixture is in Madrid, where FIXED_NOW falls on 2026-11-10.
@pytest.mark.parametrize("event_day", ["2026-11-13", "2027-01-09"])
async def test_an_event_day_3_to_60_days_after_local_today_is_accepted(
    client: AsyncClient, user: RegisteredUser, clock: Clock, event_day: str
) -> None:
    response = await create_event(client, user, event_day=event_day)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "event_day",
    ["2026-11-01", "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2027-01-10"],
)
async def test_an_event_day_not_3_to_60_days_after_local_today_returns_422(
    client: AsyncClient, user: RegisteredUser, clock: Clock, event_day: str
) -> None:
    response = await create_event(client, user, event_day=event_day)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "event_day_out_of_range"


# 23:30 on 2026-11-10 in Los Angeles, already 2026-11-11 in UTC.
LATE_IN_LOS_ANGELES = datetime(2026, 11, 11, 7, 30, tzinfo=UTC)
# 00:30 on 2026-11-11 in Auckland, still 2026-11-10 in UTC.
EARLY_IN_AUCKLAND = datetime(2026, 11, 10, 11, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("timezone", "now", "event_day", "status"),
    [
        # By UTC dates these would be 2 and 60 days away; by local dates, 3 and 61.
        ("America/Los_Angeles", LATE_IN_LOS_ANGELES, "2026-11-13", 201),
        ("America/Los_Angeles", LATE_IN_LOS_ANGELES, "2027-01-09", 201),
        ("America/Los_Angeles", LATE_IN_LOS_ANGELES, "2027-01-10", 422),
        # By UTC dates these would be 3 and 61 days away; by local dates, 2 and 60.
        ("Pacific/Auckland", EARLY_IN_AUCKLAND, "2026-11-13", 422),
        ("Pacific/Auckland", EARLY_IN_AUCKLAND, "2026-11-14", 201),
        ("Pacific/Auckland", EARLY_IN_AUCKLAND, "2027-01-10", 201),
    ],
)
async def test_the_3_and_60_day_limits_count_the_users_local_days_near_midnight(
    client: AsyncClient, clock: Clock, timezone: str, now: datetime, event_day: str, status: int
) -> None:
    traveller = await register_and_log_in(client, email="tz@example.com", timezone=timezone)
    clock.now = now

    response = await create_event(client, traveller, event_day=event_day)

    assert response.status_code == status, response.text


async def test_late_at_night_local_today_is_still_plan_day_1(
    client: AsyncClient, clock: Clock
) -> None:
    traveller = await register_and_log_in(
        client, email="tz@example.com", timezone="America/Los_Angeles"
    )
    clock.now = LATE_IN_LOS_ANGELES

    response = await create_event(client, traveller, event_day="2026-11-22")

    assert response.json()["days_until_event_day"] == 12
