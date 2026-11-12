import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import EVENTS, create_event


async def test_the_detail_matches_what_create_returned(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    created = (await create_event(client, user)).json()

    response = await client.get(f"{EVENTS}/{created['id']}", headers=user.headers)

    assert response.status_code == 200
    assert response.json() == created


# The Event Day is 2026-11-22 in Madrid; FIXED_NOW is 13:00 there on 2026-11-10.
@pytest.mark.parametrize(
    ("now", "state", "days_until"),
    [
        (FIXED_NOW + timedelta(days=11), "active", 1),
        # The last minute of the day before, and the first of the Event Day, in Madrid.
        (datetime(2026, 11, 21, 22, 59, tzinfo=UTC), "active", 1),
        (datetime(2026, 11, 21, 23, 0, tzinfo=UTC), "event_day", 0),
        (datetime(2026, 11, 22, 22, 59, tzinfo=UTC), "event_day", 0),
        (datetime(2026, 11, 22, 23, 0, tzinfo=UTC), "past", 0),
        (FIXED_NOW + timedelta(days=40), "past", 0),
    ],
)
async def test_the_state_and_countdown_follow_the_users_local_today(
    client: AsyncClient,
    user: RegisteredUser,
    clock: Clock,
    now: datetime,
    state: str,
    days_until: int,
) -> None:
    created = (await create_event(client, user, event_day="2026-11-22")).json()
    clock.now = now

    detail = (await client.get(f"{EVENTS}/{created['id']}", headers=user.headers)).json()

    assert (detail["state"], detail["days_until_event_day"]) == (state, days_until)
    assert detail["current_plan_version"] == 1


async def test_another_users_event_returns_the_same_404_as_an_unknown_id(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    other = await register_and_log_in(client, email="other@example.com")
    theirs = (await create_event(client, other)).json()

    for_theirs = await client.get(f"{EVENTS}/{theirs['id']}", headers=user.headers)
    for_unknown = await client.get(f"{EVENTS}/{uuid.uuid4()}", headers=user.headers)

    assert for_theirs.status_code == for_unknown.status_code == 404
    bodies = [r.json()["error"] for r in (for_theirs, for_unknown)]
    for body in bodies:
        del body["request_id"]
    assert bodies[0] == bodies[1]
    assert bodies[0]["code"] == "event_not_found"
