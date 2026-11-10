from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.v1.router import public_router
from app.core.config import Settings, load_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.data import common_passwords
from app.db.redis import create_redis
from app.db.session import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the DB engine and Redis pool on startup; close them on shutdown.

    HTTP clients join here when they're added.
    """
    settings: Settings = app.state.settings
    # Read the bundled password lists now, not on the first registration.
    common_passwords()
    engine = create_engine(settings)
    redis = create_redis(settings)
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


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
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CramPlan API",
        version="0.1.0",
        lifespan=lifespan,
        generate_unique_id_function=operation_id,
    )
    app.state.settings = settings
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(public_router)
    return app
