import asyncio
from functools import cache

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models.user import User


@cache
def _dummy_hash() -> str:
    """Checked against when no User has the email, so an unknown email costs the same
    argon2 work as a wrong password and response times don't reveal which emails exist.
    """
    return hash_password("no-user-has-this-password-0!")


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "Incorrect email or password"


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """The User with this email and password. `email` is already lowercased.

    Raises InvalidCredentialsError for an unknown email and a wrong password alike.
    """
    user = await session.scalar(select(User).where(User.email == email))
    password_hash = user.password_hash if user is not None else _dummy_hash()
    # argon2 is deliberately slow; keep it off the event loop.
    matches = await asyncio.to_thread(verify_password, password, password_hash)
    if user is None or not matches:
        raise InvalidCredentialsError
    return user
