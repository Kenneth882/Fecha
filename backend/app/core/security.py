import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import Settings

_passwords = CryptContext(schemes=["argon2"])

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """An argon2 hash of `password`, salted. CPU-heavy: call it off the event loop."""
    return _passwords.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Whether `password` matches `password_hash`. CPU-heavy, like hashing."""
    return _passwords.verify(password, password_hash)


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_in: int  # seconds


def create_access_token(user_id: uuid.UUID, settings: Settings) -> AccessToken:
    """A signed JWT naming `user_id` as its subject, valid for the configured lifetime."""
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    issued_at = datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": issued_at, "exp": issued_at + lifetime}
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)
    return AccessToken(token=token, expires_in=int(lifetime.total_seconds()))


def access_token_subject(token: str, settings: Settings) -> uuid.UUID | None:
    """The User id `token` names, or None if it's malformed, tampered with or expired."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None
