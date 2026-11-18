"""The migration that adds `tasks.vocab_batch_size` backfills the Tasks already stored.

It runs on the test database inside a transaction that's rolled back: Postgres DDL is
transactional, so stepping the schema back and forth here leaves it as it was.
"""

from collections.abc import Callable

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.fixtures import alembic_config

REVISION = "f8492a3929de"
MILESTONE_ID = "00000000-0000-0000-0000-000000000004"

# A User, Event, Plan and Milestone, as stored before the migration.
PRE_MIGRATION_ROWS = [
    "INSERT INTO users (id, email, password_hash, native_language, timezone) VALUES "
    "('00000000-0000-0000-0000-000000000001', 'm@example.com', 'x', 'en', 'Europe/Madrid')",
    "INSERT INTO events (id, user_id, type, target_language, event_day, level, daily_budget, "
    "created_at) VALUES ('00000000-0000-0000-0000-000000000002', "
    "'00000000-0000-0000-0000-000000000001', 'interview', 'es', '2026-11-22', 'B1', 45, "
    "'2026-11-10T12:00:00Z')",
    "INSERT INTO plans (id, event_id, version, generated_at) VALUES "
    "('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000002', 1, "
    "'2026-11-10T12:00:00Z')",
    "INSERT INTO milestones (id, plan_id, scenario_slug, position, target_date) VALUES "
    f"('{MILESTONE_ID}', '00000000-0000-0000-0000-000000000003', "
    "'interview.introducing_yourself', 1, '2026-11-12')",
]


def run_step(step: str) -> Callable[[Connection], None]:
    """Run this revision's `upgrade` or `downgrade` on a connection."""
    module = ScriptDirectory.from_config(alembic_config()).get_revision(REVISION).module

    def run(conn: Connection) -> None:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, step)()

    return run


async def test_existing_vocab_tasks_get_their_minutes_kept_between_3_and_8(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as conn:
        outer = await conn.begin()
        try:
            await conn.run_sync(run_step("downgrade"))
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

            await conn.run_sync(run_step("upgrade"))

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
