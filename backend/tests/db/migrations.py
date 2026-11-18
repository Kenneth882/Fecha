"""Helpers for tests that step one migration down and back up on the test database."""

from collections.abc import Callable

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

from tests.db.fixtures import alembic_config

MILESTONE_ID = "00000000-0000-0000-0000-000000000004"

# A User, Event, Plan and Milestone, as stored before the migrations under test.
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


def run_step(step: str, revision: str) -> Callable[[Connection], None]:
    """Run one revision's `upgrade` or `downgrade` on a connection."""
    module = ScriptDirectory.from_config(alembic_config()).get_revision(revision).module

    def run(conn: Connection) -> None:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, step)()

    return run
