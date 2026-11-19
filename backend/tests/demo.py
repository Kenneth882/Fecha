"""Helpers for API tests of the seeded demo User."""

from httpx import AsyncClient

from app.core.config import Settings
from tests.auth import RegisteredUser, log_in


async def log_in_as_demo(client: AsyncClient, settings: Settings) -> RegisteredUser:
    """The demo User, logged in with the demo credentials from settings."""
    logged_in = await log_in(client, settings.demo_email, settings.demo_password.get_secret_value())
    assert logged_in.status_code == 200, logged_in.text
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"},
    )
    return RegisteredUser(
        profile=me.json(),
        token=logged_in.json()["access_token"],
        refresh_token=logged_in.json()["refresh_token"],
    )
