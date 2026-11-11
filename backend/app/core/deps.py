from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import access_token_subject
from app.models.user import Role, User


def get_settings(request: Request) -> Settings:
    """The Settings this app was built with, as stored by `create_app`."""
    return cast(Settings, request.app.state.settings)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One async session per request, closed when the request ends.

    Tests swap it for a session inside a rolled-back transaction via
    `app.dependency_overrides[get_db]`.
    """
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session


def get_now() -> datetime:
    """The current moment, as a timezone-aware UTC datetime.

    The API's only source of "now": routes and services take it from here rather
    than calling `datetime.now()`, so tests can pin it with
    `app.dependency_overrides[get_now] = lambda: fixed_moment`. Turn it into a
    User's date with `services.local_time.local_today`.
    """
    return datetime.now(UTC)


def get_redis(request: Request) -> Redis:
    """The app's shared Redis client, opened in `lifespan`."""
    return cast(Redis, request.app.state.redis)


class NotAuthenticatedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "not_authenticated"
    message = "A valid access token is required"
    headers = {"WWW-Authenticate": "Bearer"}  # noqa: RUF012


class AdminRequiredError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "admin_required"
    message = "Only an admin can do this"


# auto_error=False: a missing header gets this app's 401 body, not FastAPI's 403.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """The User the request's bearer token names.

    Raises NotAuthenticatedError (401) if the token is missing, malformed, tampered
    with or expired, or its User no longer exists.
    """
    if credentials is None:
        raise NotAuthenticatedError
    user_id = access_token_subject(credentials.credentials, settings)
    user = await session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise NotAuthenticatedError
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """The current User, if they're an admin; AdminRequiredError (403) otherwise.

    Put it on admin routes as `Depends(require_admin)`.
    """
    if user.role != Role.ADMIN:
        raise AdminRequiredError
    return user
