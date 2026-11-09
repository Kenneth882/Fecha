from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.fixtures import alembic_head, transactional_session


async def test_the_test_schema_is_built_by_the_migrations(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as conn:
        version = await conn.scalar(text("SELECT version_num FROM alembic_version"))

    assert version == alembic_head()


async def test_writes_in_a_test_transaction_are_rolled_back_even_after_commit(
    test_engine: AsyncEngine,
) -> None:
    async with transactional_session(test_engine) as session:
        await session.execute(text("CREATE TABLE rollback_probe (id int)"))
        await session.execute(text("INSERT INTO rollback_probe VALUES (1)"))
        await session.commit()  # code under test commits; the test's writes must still vanish
        assert await session.scalar(text("SELECT count(*) FROM rollback_probe")) == 1

    async with test_engine.connect() as conn:
        table = await conn.scalar(text("SELECT to_regclass('rollback_probe')"))

    assert table is None
