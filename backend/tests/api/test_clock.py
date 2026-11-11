from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.core.deps import get_now

FIXED_NOW = datetime(2026, 11, 10, 5, 30, tzinfo=UTC)


async def now_seen_by_a_route(app: FastAPI, client: AsyncClient) -> datetime:
    """What a route receives from `get_now` when called through `client`."""
    seen: list[datetime] = []

    @app.get("/test-only/now", tags=["test"])
    async def read_now(now: Annotated[datetime, Depends(get_now)]) -> None:
        seen.append(now)

    response = await client.get("/test-only/now")
    assert response.status_code == 200
    [now] = seen
    return now


async def test_routes_see_the_overridden_clock(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_now] = lambda: FIXED_NOW

    assert await now_seen_by_a_route(app, client) == FIXED_NOW


async def test_the_real_clock_is_the_current_utc_time(app: FastAPI, client: AsyncClient) -> None:
    before = datetime.now(UTC)
    now = await now_seen_by_a_route(app, client)
    after = datetime.now(UTC)

    assert now.utcoffset() == timedelta(0)
    assert before <= now <= after
