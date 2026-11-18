"""Refresh tokens keep a User logged in, rotate on every use, and end with logout (ADR 0007)."""

import hashlib
from datetime import timedelta

from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.auth import RegisteredUser, log_in, register_and_log_in
from tests.conftest import Clock

REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


async def refresh(client: AsyncClient, token: str) -> Response:
    return await client.post(REFRESH, json={"refresh_token": token})


async def test_logging_in_also_returns_a_refresh_token_lasting_30_days(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    response = await log_in(client, user.profile["email"])

    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == 30 * 60
    assert isinstance(body["refresh_token"], str) and len(body["refresh_token"]) >= 43
    assert body["refresh_expires_in"] == 30 * 24 * 60 * 60
    assert body["refresh_token"] != user.refresh_token


async def test_only_a_hash_of_the_refresh_token_is_stored(
    client: AsyncClient, clock: Clock, user: RegisteredUser, db_session: AsyncSession
) -> None:
    rows = await db_session.execute(
        text("SELECT token_hash FROM refresh_tokens WHERE user_id = :id"),
        {"id": user.profile["id"]},
    )

    assert [row.token_hash for row in rows] == [
        hashlib.sha256(user.refresh_token.encode()).hexdigest()
    ]
    stored = await db_session.execute(text("SELECT * FROM refresh_tokens"))
    assert user.refresh_token not in str(stored.all())


async def test_refreshing_returns_a_working_access_token_and_a_new_refresh_token(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    clock.now += timedelta(hours=1)

    response = await refresh(client, user.refresh_token)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "access_token",
        "token_type",
        "expires_in",
        "refresh_token",
        "refresh_expires_in",
    }
    assert body["refresh_token"] != user.refresh_token
    me = await client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.profile["id"]


def assert_refresh_refused(response: Response) -> None:
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


async def test_an_unknown_refresh_token_is_refused(client: AsyncClient, clock: Clock) -> None:
    assert_refresh_refused(await refresh(client, "not-a-token-anyone-was-given"))


async def test_a_rotated_refresh_token_is_refused(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    assert (await refresh(client, user.refresh_token)).status_code == 200

    assert_refresh_refused(await refresh(client, user.refresh_token))


async def test_reusing_a_rotated_token_revokes_every_session_of_the_user(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    other_device = (await log_in(client, user.profile["email"])).json()["refresh_token"]
    rotated = (await refresh(client, user.refresh_token)).json()["refresh_token"]

    # A thief replays the token the User has already swapped.
    assert_refresh_refused(await refresh(client, user.refresh_token))

    assert_refresh_refused(await refresh(client, rotated))
    assert_refresh_refused(await refresh(client, other_device))


async def test_reuse_leaves_other_users_sessions_alone(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    other = await register_and_log_in(client, email="bea@example.com")
    await refresh(client, user.refresh_token)
    await refresh(client, user.refresh_token)

    assert (await refresh(client, other.refresh_token)).status_code == 200


async def test_a_session_idle_for_30_days_expires(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    clock.now += timedelta(days=30)

    assert_refresh_refused(await refresh(client, user.refresh_token))


async def test_a_session_used_within_30_days_keeps_going(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    token = user.refresh_token
    for _ in range(3):
        clock.now += timedelta(days=29)
        response = await refresh(client, token)
        assert response.status_code == 200
        token = response.json()["refresh_token"]


async def test_a_session_ends_90_days_after_the_first_login_however_often_it_is_used(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    token = user.refresh_token
    for _ in range(4):  # days 20, 40, 60, 80
        clock.now += timedelta(days=20)
        response = await refresh(client, token)
        assert response.status_code == 200
        token = response.json()["refresh_token"]
    # Day 80: the token now lasts only until the cap, 10 days away, not 30.
    assert response.json()["refresh_expires_in"] == 10 * 24 * 60 * 60

    clock.now += timedelta(days=10)

    assert_refresh_refused(await refresh(client, token))


async def test_logging_out_revokes_the_refresh_token(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    response = await client.post(
        LOGOUT, json={"refresh_token": user.refresh_token}, headers=user.headers
    )

    assert response.status_code == 204
    assert_refresh_refused(await refresh(client, user.refresh_token))


async def test_logging_out_revokes_the_whole_family_but_not_other_sessions(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    other_device = (await log_in(client, user.profile["email"])).json()["refresh_token"]
    rotated = (await refresh(client, user.refresh_token)).json()["refresh_token"]

    # Logging out with an earlier token of the same session still ends all of it.
    response = await client.post(
        LOGOUT, json={"refresh_token": user.refresh_token}, headers=user.headers
    )

    assert response.status_code == 204
    assert (await refresh(client, other_device)).status_code == 200
    # Last: a revoked token presented again counts as reuse and ends every session.
    assert_refresh_refused(await refresh(client, rotated))


async def test_logout_cannot_end_another_users_session(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    other = await register_and_log_in(client, email="bea@example.com")

    response = await client.post(
        LOGOUT, json={"refresh_token": other.refresh_token}, headers=user.headers
    )

    assert response.status_code == 204
    assert (await refresh(client, other.refresh_token)).status_code == 200


async def test_logout_needs_an_access_token(
    client: AsyncClient, clock: Clock, user: RegisteredUser
) -> None:
    response = await client.post(LOGOUT, json={"refresh_token": user.refresh_token})

    assert response.status_code == 401
    assert (await refresh(client, user.refresh_token)).status_code == 200
