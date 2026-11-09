"""The test database: built once per session from the migrations, one rolled-back
transaction per test."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str | None = None) -> Config:
    """Config without the ini file, so tests keep their own logging.

    env.py takes `database_url` from here; without one, it's only good for reading scripts.
    """
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if database_url is not None:
        config.attributes["database_url"] = database_url
    return config


def alembic_head() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


async def build_test_schema(engine: AsyncEngine) -> None:
    """Wipe the test database, then build it by running every migration.

    Refuses any database whose name doesn't end in `_test`, so a misconfigured
    TEST_DATABASE_URL can never wipe dev data.
    """
    url = engine.url
    if not (url.database or "").endswith("_test"):
        raise RuntimeError(f"Refusing to wipe {url.database!r}: test database names end in _test")
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    # env.py calls asyncio.run(), which can't nest inside the running test loop.
    config = alembic_config(url.render_as_string(hide_password=False))
    await asyncio.to_thread(command.upgrade, config, "head")


@asynccontextmanager
async def transactional_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that's always rolled back.

    The session's own commits become savepoints, so code under test can commit
    freely and its writes still vanish when the block exits.
    """
    async with engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()
