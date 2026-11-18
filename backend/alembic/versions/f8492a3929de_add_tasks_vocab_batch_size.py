"""add tasks vocab_batch_size

Revision ID: f8492a3929de
Revises: e4b1de05011f
Create Date: 2026-11-18 14:29:59.745951

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8492a3929de"
down_revision: str | Sequence[str] | None = "e4b1de05011f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add how many Vocab Items each Vocab Task teaches (ADR 0006).

    Existing Vocab Tasks get their minutes kept between 3 and 8, the planner's rule
    before its cap. The backfill is plain SQL, so later changes to the app can't change
    what this migration does.
    """
    op.add_column("tasks", sa.Column("vocab_batch_size", sa.SmallInteger(), nullable=True))
    op.execute(
        "UPDATE tasks SET vocab_batch_size = LEAST(GREATEST(estimated_minutes, 3), 8) "
        "WHERE kind = 'vocab'"
    )
    op.create_check_constraint(
        op.f("ck_tasks_vocab_batch_size"),
        "tasks",
        "(kind = 'vocab') = (vocab_batch_size IS NOT NULL)",
    )


def downgrade() -> None:
    """Drop tasks.vocab_batch_size and its check."""
    op.drop_constraint(op.f("ck_tasks_vocab_batch_size"), "tasks", type_="check")
    op.drop_column("tasks", "vocab_batch_size")
