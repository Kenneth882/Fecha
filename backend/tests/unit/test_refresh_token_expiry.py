"""A refresh token's expiry: 30 days after its last use, never past the session's 90-day cap."""

from datetime import UTC, datetime, timedelta

from app.core.security import refresh_token_expiry

LOGIN = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
IDLE = timedelta(days=30)
ABSOLUTE = timedelta(days=90)


def test_a_new_session_expires_after_the_idle_limit() -> None:
    assert refresh_token_expiry(LOGIN, LOGIN, IDLE, ABSOLUTE) == datetime(
        2026, 12, 10, 12, 0, tzinfo=UTC
    )


def test_each_use_slides_the_expiry_forward() -> None:
    used = LOGIN + timedelta(days=20)

    assert refresh_token_expiry(used, LOGIN, IDLE, ABSOLUTE) == datetime(
        2026, 12, 30, 12, 0, tzinfo=UTC
    )


def test_the_expiry_never_passes_the_absolute_cap_from_the_first_login() -> None:
    used = LOGIN + timedelta(days=75)

    assert refresh_token_expiry(used, LOGIN, IDLE, ABSOLUTE) == datetime(
        2027, 2, 8, 12, 0, tzinfo=UTC
    )
