"""The migration that adds `tasks.vocab_batch_size` backfills the Tasks already stored.

It runs on the test database inside a transaction that's rolled back: Postgres DDL is
transactional, so stepping the schema back and forth here leaves it as it was.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.migrations import MILESTONE_ID, PRE_MIGRATION_ROWS, run_step

REVISION = "f8492a3929de"


async def test_existing_vocab_tasks_get_their_minutes_kept_between_3_and_8(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as conn:
        outer = await conn.begin()
        try:
            await conn.run_sync(run_step("downgrade", REVISION))
            for statement in PRE_MIGRATION_ROWS:
                await conn.execute(text(statement))
            for position, (kind, minutes) in enumerate(
                [("vocab", 2), ("vocab", 5), ("vocab", 9), ("listen", 5), ("speak", 9)], start=1
            ):
                await conn.execute(
                    text(
                        "INSERT INTO tasks (id, milestone_id, date, kind, position, "
                        "estimated_minutes) VALUES (gen_random_uuid(), :milestone, "
                        "'2026-11-10', :kind, :position, :minutes)"
                    ),
                    {
                        "milestone": MILESTONE_ID,
                        "kind": kind,
                        "position": position,
                        "minutes": minutes,
                    },
                )

            await conn.run_sync(run_step("upgrade", REVISION))

            rows = await conn.execute(
                text("SELECT kind, vocab_batch_size FROM tasks ORDER BY position")
            )
            assert [tuple(row) for row in rows] == [
                ("vocab", 3),
                ("vocab", 5),
                ("vocab", 8),
                ("listen", None),
                ("speak", None),
            ]
            # From now on, a Vocab Task without a batch size is refused.
            with pytest.raises(IntegrityError, match="ck_tasks_vocab_batch_size"):
                async with conn.begin_nested():
                    await conn.execute(text("UPDATE tasks SET vocab_batch_size = NULL"))
        finally:
            await outer.rollback()
