from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.core.deps import get_now

FIXED_NOW = datetime(2026, 11, 10, 5, 30, tzinfo=UTC)


async def test_routes_see_the_overridden_clock(app: FastAPI, client: AsyncClient) -> None:
    seen: list[datetime] = []

    @app.get("/test-only/now", tags=["test"])
    async def read_now(now: Annotated[datetime, Depends(get_now)]) -> None:
        seen.append(now)

    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    response = await client.get("/test-only/now")

    assert response.status_code == 200
    assert seen == [FIXED_NOW]


async def test_the_real_clock_is_the_current_utc_time(app: FastAPI, client: AsyncClient) -> None:
    seen: list[datetime] = []

    @app.get("/test-only/now", tags=["test"])
    async def read_now(now: Annotated[datetime, Depends(get_now)]) -> None:
        seen.append(now)

    before = datetime.now(UTC)
    await client.get("/test-only/now")
    after = datetime.now(UTC)

    [now] = seen
    assert now.utcoffset() == timedelta(0)
    assert before <= now <= after
