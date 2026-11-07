from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import Settings, load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup/shutdown of the DB engine, Redis pool and HTTP clients goes here.
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. With no settings given, reads them from the environment."""
    if settings is None:
        settings = load_settings()
    app = FastAPI(title="CramPlan API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(api_router)
    return app
