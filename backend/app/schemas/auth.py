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
    """A short-lived access token, sent as `Authorization: Bearer <access_token>`."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Seconds until the token expires.
    expires_in: int
