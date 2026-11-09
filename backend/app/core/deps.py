from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings


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


def get_redis(request: Request) -> Redis:
    """The app's shared Redis client, opened in `lifespan`."""
    return cast(Redis, request.app.state.redis)
