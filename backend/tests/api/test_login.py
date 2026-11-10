from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.auth import GOOD_PASSWORD, RegisteredUser, log_in, register
from tests.conftest import TEST_JWT_SECRET

ME = "/api/v1/auth/me"


async def test_logging_in_with_correct_credentials_returns_a_bearer_token(
    client: AsyncClient,
) -> None:
    await register(client, email="ana@example.com")

    response = await log_in(client, "ana@example.com")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    assert isinstance(body["access_token"], str) and body["access_token"]


@pytest.mark.parametrize("typed", ["Ana@Example.COM", "  ana@example.com  "])
async def test_the_email_is_matched_ignoring_letter_case_and_surrounding_spaces(
    client: AsyncClient, typed: str
) -> None:
    await register(client, email="ana@example.com")

    response = await log_in(client, typed)

    assert response.status_code == 200


async def test_a_wrong_password_and_an_unknown_email_get_the_same_401(client: AsyncClient) -> None:
    await register(client, email="ana@example.com")

    wrong_password = await log_in(client, "ana@example.com", "wrong-kettle-47-harbor")
    unknown_email = await log_in(client, "nobody@example.com", GOOD_PASSWORD)

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        error = response.json()["error"]
        assert (error["code"], error["message"]) == (
            "invalid_credentials",
            "Incorrect email or password",
        )


async def test_me_with_a_valid_token_returns_the_users_profile_without_the_hash(
    client: AsyncClient, user: RegisteredUser
) -> None:
    response = await client.get(ME, headers=user.headers)

    assert response.status_code == 200
    assert response.json() == user.profile
    assert "$argon2" not in response.text
    assert "password" not in response.text.lower()


def signed(claims: dict[str, Any], secret: str = TEST_JWT_SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, secret, algorithm=algorithm)


def claims_for(user: RegisteredUser, **overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": user.profile["id"],
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    claims.update(overrides)
    return claims


def assert_not_authenticated(response: Any) -> None:
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_me_without_a_token_returns_401(client: AsyncClient) -> None:
    assert_not_authenticated(await client.get(ME))


@pytest.mark.parametrize(
    "authorization",
    ["Bearer not-a-jwt", "Bearer ", "Basic YW5hOnB3", "not-even-a-scheme"],
)
async def test_me_with_a_malformed_authorization_header_returns_401(
    client: AsyncClient, authorization: str
) -> None:
    assert_not_authenticated(await client.get(ME, headers={"Authorization": authorization}))


async def test_me_with_a_tampered_token_returns_401(
    client: AsyncClient, user: RegisteredUser
) -> None:
    header, _payload, signature = user.token.split(".")
    # The same User's claims with a year-long expiry, under the original signature:
    # only the signature check can catch it.
    a_year_on = datetime.now(UTC) + timedelta(days=365)
    forged = jwt.encode(claims_for(user, exp=a_year_on), "x" * 32).split(".")[1]

    response = await client.get(
        ME, headers={"Authorization": f"Bearer {header}.{forged}.{signature}"}
    )

    assert_not_authenticated(response)


@pytest.mark.parametrize(
    "token_for",
    [
        pytest.param(
            lambda u: signed(claims_for(u), secret="another-secret-" + "z" * 32), id="wrong-key"
        ),
        pytest.param(
            lambda u: signed(
                claims_for(
                    u,
                    iat=datetime.now(UTC) - timedelta(hours=1),
                    exp=datetime.now(UTC) - timedelta(seconds=1),
                )
            ),
            id="expired",
        ),
        pytest.param(
            lambda u: signed({k: v for k, v in claims_for(u).items() if k != "exp"}), id="no-expiry"
        ),
        pytest.param(lambda u: signed(claims_for(u, sub="not-a-uuid")), id="subject-not-a-uuid"),
        pytest.param(
            lambda u: signed({k: v for k, v in claims_for(u).items() if k != "sub"}),
            id="no-subject",
        ),
        pytest.param(lambda u: jwt.encode(claims_for(u), None, algorithm="none"), id="alg-none"),
    ],
)
async def test_me_with_an_invalid_token_returns_401(
    client: AsyncClient, user: RegisteredUser, token_for: Any
) -> None:
    response = await client.get(ME, headers={"Authorization": f"Bearer {token_for(user)}"})

    assert_not_authenticated(response)


async def test_me_with_a_valid_token_whose_user_no_longer_exists_returns_401(
    client: AsyncClient, user: RegisteredUser, db_session: AsyncSession
) -> None:
    # No API deletes Users yet, so the row goes directly.
    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.profile["id"]})

    assert_not_authenticated(await client.get(ME, headers=user.headers))


async def test_me_accepts_a_token_signed_independently_with_the_app_secret(
    client: AsyncClient, user: RegisteredUser
) -> None:
    # Pins the token format: HS256 with the configured secret, subject = User id.
    response = await client.get(ME, headers={"Authorization": f"Bearer {signed(claims_for(user))}"})

    assert response.status_code == 200
    assert response.json()["id"] == user.profile["id"]
