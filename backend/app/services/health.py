import asyncio
from collections.abc import Awaitable

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.health import CheckStatus, ReadinessChecks, ReadinessResponse

# A probe must answer quickly even when a dependency hangs rather than refusing.
CHECK_TIMEOUT_SEC = 2.0


async def _check(probe: Awaitable[object]) -> CheckStatus:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SEC):
            await probe
    except Exception:
        return "unavailable"
    return "ok"


async def _ping_postgres(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))


async def check_readiness(session: AsyncSession, redis: Redis) -> ReadinessResponse:
    """Whether Postgres and Redis both answer, checked concurrently."""
    postgres_status, redis_status = await asyncio.gather(
        _check(_ping_postgres(session)), _check(redis.ping())
    )
    overall: CheckStatus = "ok" if postgres_status == redis_status == "ok" else "unavailable"
    return ReadinessResponse(
        status=overall, checks=ReadinessChecks(postgres=postgres_status, redis=redis_status)
    )
