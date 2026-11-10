import uuid
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password

REGISTER = "/api/v1/auth/register"

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


async def test_registering_returns_201_with_the_user_profile(client: AsyncClient) -> None:
    response = await register(client)

    assert response.status_code == 201
    profile = response.json()
    assert set(profile) == {"id", "email", "timezone", "native_language", "role", "created_at"}
    uuid.UUID(profile["id"])
    assert profile["email"] == "ana@example.com"
    assert profile["timezone"] == "Europe/Madrid"
    assert profile["native_language"] == "en"
    assert profile["role"] == "user"
    assert datetime.fromisoformat(profile["created_at"]).tzinfo is not None


async def test_native_language_defaults_to_english_when_omitted(client: AsyncClient) -> None:
    body = registration()
    del body["native_language"]

    response = await client.post(REGISTER, json=body)

    assert response.status_code == 201
    assert response.json()["native_language"] == "en"


async def test_a_native_language_other_than_english_returns_422(client: AsyncClient) -> None:
    response = await register(client, native_language="es")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "timezone",
    ["Mars/Olympus_Mons", "europe/madrid", "", "../../etc/passwd", "/etc/localtime", "GMT+2"],
)
async def test_a_timezone_that_is_not_an_iana_name_returns_422(
    client: AsyncClient, timezone: str
) -> None:
    response = await register(client, timezone=timezone)

    assert response.status_code == 422


@pytest.mark.parametrize("timezone", ["America/Argentina/Buenos_Aires", "UTC", "Asia/Kolkata"])
async def test_any_iana_timezone_is_accepted(client: AsyncClient, timezone: str) -> None:
    response = await register(client, timezone=timezone)

    assert response.status_code == 201
    assert response.json()["timezone"] == timezone


def error_codes(response: Response) -> list[tuple[str | None, str]]:
    return [(d["field"], d["code"]) for d in response.json()["error"]["details"]]


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("a1!bcde", "password_too_short"),
        ("violet-kettle-harbor", "password_no_digit"),
        ("violetkettle47harbor", "password_no_special_character"),
        # On the bundled list in some casing, though it meets every other rule.
        ("Password1!", "password_too_common"),
        ("P@ssw0rd", "password_too_common"),
    ],
)
async def test_a_password_breaking_a_rule_returns_422_naming_the_rule(
    client: AsyncClient, password: str, code: str
) -> None:
    response = await register(client, password=password)

    assert response.status_code == 422
    assert error_codes(response) == [("password", code)]


async def test_the_email_is_stored_lowercased(client: AsyncClient) -> None:
    response = await register(client, email="Ana.Lopez@Example.COM")

    assert response.status_code == 201
    assert response.json()["email"] == "ana.lopez@example.com"


@pytest.mark.parametrize("again", ["ana@example.com", "ANA@example.com", "Ana@Example.Com"])
async def test_an_email_already_in_use_in_any_letter_case_returns_409(
    client: AsyncClient, again: str
) -> None:
    await register(client, email="ana@example.com")

    response = await register(client, email=again)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_an_invalid_email_returns_422(client: AsyncClient) -> None:
    response = await register(client, email="not-an-email")

    assert response.status_code == 422
    assert error_codes(response) == [("email", "value_error")]


async def test_the_email_is_stored_lowercased_and_the_password_only_as_an_argon2_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client, email="Ana@Example.COM")

    # The one direct DB read in these tests: nothing in the API exposes the stored row.
    row = (await db_session.execute(text("SELECT * FROM users"))).one()

    assert row.email == "ana@example.com"
    assert row.password_hash.startswith("$argon2id$")
    assert verify_password(GOOD_PASSWORD, row.password_hash)
    assert GOOD_PASSWORD not in [str(value) for value in row]


async def test_no_response_carries_the_password_or_its_hash(client: AsyncClient) -> None:
    created = await register(client)
    duplicate = await register(client)

    for response in (created, duplicate):
        assert "$argon2" not in response.text
        assert GOOD_PASSWORD not in response.text
        assert "password" not in response.text.lower()


async def test_a_very_long_password_returns_422_not_500(client: AsyncClient) -> None:
    # Over passlib's 4,096-byte limit, which once crashed hashing with a 500.
    response = await register(client, password="a1!" + "q" * 4997)

    assert response.status_code == 422
    assert error_codes(response) == [("password", "password_too_long")]


async def test_a_128_character_password_of_multibyte_characters_is_accepted(
    client: AsyncClient,
) -> None:
    # 128 characters but 509 bytes in UTF-8: the limit counts characters.
    response = await register(client, password="7" + "🔑" * 127)

    assert response.status_code == 201


async def test_a_submitted_role_is_ignored(client: AsyncClient) -> None:
    # Only the server decides roles; a client asking for admin gets a plain User.
    response = await register(client, role="admin")

    assert response.status_code == 201
    assert response.json()["role"] == "user"
