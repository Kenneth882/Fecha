"""The migration that adds Vocab Task batches, Review States and Reviews steps down and
back up cleanly, and leaves existing Vocab Tasks with no batch fixed.

It runs inside a transaction that's rolled back, like test_vocab_batch_size_migration.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.migrations import MILESTONE_ID, PRE_MIGRATION_ROWS, run_step

REVISION = "7b9d6eed83c4"


async def test_downgrade_then_upgrade_keeps_existing_tasks_with_no_batch_fixed(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as conn:
        outer = await conn.begin()
        try:
            await conn.run_sync(run_step("downgrade", REVISION))
            for statement in PRE_MIGRATION_ROWS:
                await conn.execute(text(statement))
            await conn.execute(
                text(
                    "INSERT INTO tasks (id, milestone_id, date, kind, position, "
                    "estimated_minutes, vocab_batch_size) VALUES (gen_random_uuid(), "
                    ":milestone, '2026-11-10', 'vocab', 1, 6, 6)"
                ),
                {"milestone": MILESTONE_ID},
            )
            tables = "SELECT to_regclass('review_states'), to_regclass('reviews')"
            assert tuple((await conn.execute(text(tables))).one()) == (None, None)

            await conn.run_sync(run_step("upgrade", REVISION))

            fixed_at = await conn.scalar(text("SELECT vocab_batch_fixed_at FROM tasks"))
            assert fixed_at is None
            for table in ("vocab_task_items", "review_states", "reviews"):
                assert await conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        finally:
            await outer.rollback()
