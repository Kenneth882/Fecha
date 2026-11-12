import uuid
from datetime import timedelta

from httpx import AsyncClient

from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import EVENTS, abandon, create_event


async def test_abandoning_returns_the_event_as_past_and_it_stays_readable(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    created = (await create_event(client, user)).json()
    clock.now = FIXED_NOW + timedelta(hours=2)

    response = await abandon(client, user, created["id"])

    assert response.status_code == 200, response.text
    abandoned = response.json()
    assert abandoned["state"] == "past"
    assert abandoned["abandoned_at"] == "2026-11-10T14:00:00Z"
    unchanged = {k: v for k, v in created.items() if k not in ("state", "abandoned_at")}
    assert {k: abandoned[k] for k in unchanged} == unchanged
    detail = await client.get(f"{EVENTS}/{created['id']}", headers=user.headers)
    assert detail.json() == abandoned


async def test_after_abandoning_a_new_event_can_be_created(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    abandoned = (await create_event(client, user)).json()
    await abandon(client, user, abandoned["id"])
    # A later created_at than the abandoned Event's, so "newest first" is defined.
    clock.now = FIXED_NOW + timedelta(minutes=5)

    response = await create_event(client, user, type="speech", event_day="2026-12-01")

    assert response.status_code == 201, response.text
    listed = (await client.get(EVENTS, headers=user.headers)).json()
    assert [(e["id"], e["state"]) for e in listed] == [
        (response.json()["id"], "active"),
        (abandoned["id"], "past"),
    ]


async def test_the_event_can_be_abandoned_on_its_event_day(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    created = (await create_event(client, user, event_day="2026-11-22")).json()
    clock.now = FIXED_NOW + timedelta(days=12)

    response = await abandon(client, user, created["id"])

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "past"


async def test_abandoning_an_already_abandoned_event_returns_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    created = (await create_event(client, user)).json()
    first = (await abandon(client, user, created["id"])).json()
    clock.now = FIXED_NOW + timedelta(hours=1)

    response = await abandon(client, user, created["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_already_past"
    detail = await client.get(f"{EVENTS}/{created['id']}", headers=user.headers)
    assert detail.json()["abandoned_at"] == first["abandoned_at"]


async def test_abandoning_an_event_after_its_event_day_returns_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    created = (await create_event(client, user, event_day="2026-11-22")).json()
    clock.now = FIXED_NOW + timedelta(days=13)

    response = await abandon(client, user, created["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_already_past"
    detail = await client.get(f"{EVENTS}/{created['id']}", headers=user.headers)
    assert detail.json()["abandoned_at"] is None


async def test_abandoning_another_users_event_returns_404_and_leaves_it_active(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    other = await register_and_log_in(client, email="other@example.com")
    theirs = (await create_event(client, other)).json()

    for_theirs = await abandon(client, user, theirs["id"])
    for_unknown = await abandon(client, user, uuid.uuid4())

    assert for_theirs.status_code == for_unknown.status_code == 404
    assert for_theirs.json()["error"]["code"] == "event_not_found"
    detail = await client.get(f"{EVENTS}/{theirs['id']}", headers=other.headers)
    assert detail.json()["state"] == "active"
