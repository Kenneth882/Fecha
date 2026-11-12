from datetime import timedelta

from httpx import AsyncClient

from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import EVENTS, create_event


async def test_the_list_shows_only_my_events_newest_first_with_their_states(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    # FIXED_NOW is 2026-11-10 in Madrid. Each Event Day passes before the next create.
    first = (await create_event(client, user, event_day="2026-11-13")).json()
    clock.now = FIXED_NOW + timedelta(days=4)
    second = (await create_event(client, user, event_day="2026-11-20")).json()
    clock.now = FIXED_NOW + timedelta(days=11)
    third = (await create_event(client, user, event_day="2026-11-25")).json()
    other = await register_and_log_in(client, email="other@example.com")
    await create_event(client, other, event_day="2026-11-25")

    response = await client.get(EVENTS, headers=user.headers)

    assert response.status_code == 200
    listed = [(e["id"], e["state"]) for e in response.json()]
    assert listed == [(third["id"], "active"), (second["id"], "past"), (first["id"], "past")]


async def test_an_event_on_its_event_day_is_listed_as_event_day(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    await create_event(client, user, event_day="2026-11-22")
    clock.now = FIXED_NOW + timedelta(days=12)

    response = await client.get(EVENTS, headers=user.headers)

    assert [e["state"] for e in response.json()] == ["event_day"]


async def test_a_user_with_no_events_gets_an_empty_list(
    client: AsyncClient, user: RegisteredUser
) -> None:
    response = await client.get(EVENTS, headers=user.headers)

    assert response.status_code == 200
    assert response.json() == []
