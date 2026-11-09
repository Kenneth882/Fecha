from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.v1.router import public_router
from app.core.config import Settings, load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup/shutdown of the DB engine, Redis pool and HTTP clients goes here.
    yield


def operation_id(route: APIRoute) -> str:
    """`{tag}-{route name}`, e.g. `health-liveness`: the names the generated TS client uses.

    FastAPI calls this while registering every route, so it must never raise: a bad
    route would take the whole app down. tests/api/test_openapi.py enforces the
    one-tag rule for routes in the schema instead.
    """
    tag = str(route.tags[0]) if route.tags else ""
    return f"{tag}-{route.name}"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. With no settings given, reads them from the environment.

    Run it with `uvicorn --factory app.main:create_app`.
    """
    if settings is None:
        settings = load_settings()
    app = FastAPI(
        title="CramPlan API",
        version="0.1.0",
        lifespan=lifespan,
        generate_unique_id_function=operation_id,
    )
    app.state.settings = settings
    app.include_router(public_router)
    return app
