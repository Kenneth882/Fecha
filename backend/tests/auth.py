"""Helpers for API tests that need a registered User, and a token to act as them."""

from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient, Response

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"

# Long, with a digit and a special character, and on no common-password list.
GOOD_PASSWORD = "violet-kettle-47-harbor"


def registration(**overrides: Any) -> dict[str, Any]:
    """A valid registration body; keyword arguments replace or add fields."""
    body: dict[str, Any] = {
        "email": "ana@example.com",
        "password": GOOD_PASSWORD,
        "timezone": "Europe/Madrid",
        "native_language": "en",
    }
    body.update(overrides)
    return body


async def register(client: AsyncClient, **overrides: Any) -> Response:
    return await client.post(REGISTER, json=registration(**overrides))


async def log_in(client: AsyncClient, email: str, password: str = GOOD_PASSWORD) -> Response:
    return await client.post(LOGIN, json={"email": email, "password": password})


@dataclass(frozen=True)
class RegisteredUser:
    """A User created through the API, logged in."""

    profile: dict[str, Any]
    token: str

    @property
    def headers(self) -> dict[str, str]:
        """Send these to act as this User."""
        return {"Authorization": f"Bearer {self.token}"}


async def register_and_log_in(client: AsyncClient, **overrides: Any) -> RegisteredUser:
    """Register a User (fields as in `registration`) and log them in."""
    body = registration(**overrides)
    registered = await register(client, **body)
    assert registered.status_code == 201, registered.text
    logged_in = await log_in(client, body["email"], body["password"])
    assert logged_in.status_code == 200, logged_in.text
    return RegisteredUser(
        profile=registered.json(),
        token=logged_in.json()["access_token"],
    )
