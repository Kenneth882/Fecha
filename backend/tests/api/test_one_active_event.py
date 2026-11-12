from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import create_event


async def test_a_second_event_while_one_is_active_returns_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    await create_event(client, user)

    response = await create_event(client, user, type="speech", event_day="2026-12-01")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "active_event_exists"


async def test_an_event_on_its_event_day_is_still_the_active_event(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    await create_event(client, user, event_day="2026-11-22")
    clock.now = FIXED_NOW + timedelta(days=12)

    response = await create_event(client, user, event_day="2026-12-01")

    assert response.status_code == 409


async def test_once_the_event_day_has_passed_a_new_event_can_be_created(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    await create_event(client, user, event_day="2026-11-22")
    clock.now = FIXED_NOW + timedelta(days=13)

    response = await create_event(client, user, event_day="2026-12-10")

    assert response.status_code == 201, response.text


async def test_another_users_active_event_does_not_block_mine(
    client: AsyncClient, user: RegisteredUser, clock: Clock
) -> None:
    other = await register_and_log_in(client, email="other@example.com")
    await create_event(client, other)

    response = await create_event(client, user)

    assert response.status_code == 201, response.text


@pytest.fixture
async def statements(db_session: AsyncSession) -> list[str]:
    """Every SQL statement the test's session runs from here on, in order."""
    seen: list[str] = []
    conn = await db_session.connection()

    def record(*args: Any) -> None:
        seen.append(" ".join(args[2].split()))

    event.listen(conn.sync_connection, "before_cursor_execute", record)
    return seen


async def test_creating_locks_the_users_row_before_checking_and_inserting(
    client: AsyncClient, user: RegisteredUser, clock: Clock, statements: list[str]
) -> None:
    # A double-submitted form must not create two Active Events. No database
    # constraint can say "one Active Event" (ADR 0005), so creates for one User are
    # serialised on their row; a true two-connection race can't run in the shared
    # test transaction.
    await create_event(client, user)

    lock = next(i for i, s in enumerate(statements) if "FROM users" in s and "FOR UPDATE" in s)
    check = next(i for i, s in enumerate(statements) if s.startswith("SELECT") and "events" in s)
    insert = next(i for i, s in enumerate(statements) if s.startswith("INSERT INTO events"))
    assert lock < check < insert
