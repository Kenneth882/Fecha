from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.services.password_policy import MAX_LENGTH as PASSWORD_MAX_LENGTH


class LoginRequest(BaseModel):
    """What a person sends to log in."""

    # Not validated as an email: a malformed one simply matches no User. Lowercased,
    # as registration stores it, so matching ignores letter case.
    email: Annotated[str, StringConstraints(max_length=320, strip_whitespace=True, to_lower=True)]
    # No registered password is longer, and the cap keeps oversized input away from
    # the hasher.
    password: Annotated[str, StringConstraints(max_length=PASSWORD_MAX_LENGTH)]


class TokenResponse(BaseModel):
    """A short-lived access token, sent as `Authorization: Bearer <access_token>`, and
    the refresh token that gets the next one from `/auth/refresh` (ADR 0007)."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Seconds until the access token expires.
    expires_in: int
    # Single use: each refresh returns a new one and revokes this one.
    refresh_token: str
    # Seconds until the refresh token expires if it isn't used first.
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    """A refresh token, sent to `/auth/refresh` to rotate it or `/auth/logout` to revoke it."""

    # Real tokens are 43 characters; the cap keeps junk input small.
    refresh_token: Annotated[str, StringConstraints(max_length=128)]
