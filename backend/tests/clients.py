from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A client for `app` with its lifespan run, as uvicorn would on startup/shutdown."""
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client
