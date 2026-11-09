from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """The app's one engine. It connects lazily, so creating it never touches Postgres."""
    return create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Sessions keep loaded attributes after commit, so responses can read them."""
    return async_sessionmaker(engine, expire_on_commit=False)
