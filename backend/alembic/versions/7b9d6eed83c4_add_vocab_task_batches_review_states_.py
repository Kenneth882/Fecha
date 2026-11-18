"""add vocab task batches, review states and reviews

Revision ID: 7b9d6eed83c4
Revises: f8492a3929de
Create Date: 2026-11-18 15:03:03.376079

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b9d6eed83c4"
down_revision: str | Sequence[str] | None = "f8492a3929de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Vocab Task batches, Review States and the Review log (#42).

    Existing Vocab Tasks keep a null `vocab_batch_fixed_at`: their batch is chosen the
    first time they're opened or completed.
    """
    op.create_table(
        "review_states",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("vocab_item_id", sa.Uuid(), nullable=False),
        sa.Column("introduced_on", sa.Date(), nullable=False),
        sa.Column("ease", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.SmallInteger(), nullable=False),
        sa.Column("repetitions", sa.SmallInteger(), nullable=False),
        sa.Column("lapses", sa.SmallInteger(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("reviewed_in_final_window", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_review_states_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vocab_item_id"],
            ["vocab_items.id"],
            name=op.f("fk_review_states_vocab_item_id_vocab_items"),
        ),
        sa.PrimaryKeyConstraint("event_id", "vocab_item_id", name=op.f("pk_review_states")),
    )
    op.create_index(
        "ix_review_states_event_id_due_on", "review_states", ["event_id", "due_on"], unique=False
    )
    op.create_index(
        op.f("ix_review_states_vocab_item_id"), "review_states", ["vocab_item_id"], unique=False
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("vocab_item_id", sa.Uuid(), nullable=False),
        sa.Column("plan_day", sa.Date(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("grade BETWEEN 0 AND 5", name=op.f("ck_reviews_grade")),
        sa.ForeignKeyConstraint(
            ["event_id", "vocab_item_id"],
            ["review_states.event_id", "review_states.vocab_item_id"],
            name=op.f("fk_reviews_event_id_review_states"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
    )
    op.create_index(
        "ix_reviews_event_id_vocab_item_id", "reviews", ["event_id", "vocab_item_id"], unique=False
    )
    op.create_table(
        "vocab_task_items",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("vocab_item_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("position >= 1", name=op.f("ck_vocab_task_items_position")),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_vocab_task_items_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vocab_item_id"],
            ["vocab_items.id"],
            name=op.f("fk_vocab_task_items_vocab_item_id_vocab_items"),
        ),
        sa.PrimaryKeyConstraint("task_id", "position", name=op.f("pk_vocab_task_items")),
        sa.UniqueConstraint("task_id", "vocab_item_id", name=op.f("uq_vocab_task_items_task_id")),
    )
    op.create_index(
        op.f("ix_vocab_task_items_vocab_item_id"),
        "vocab_task_items",
        ["vocab_item_id"],
        unique=False,
    )
    op.add_column(
        "tasks", sa.Column("vocab_batch_fixed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Drop the Review log, Review States and Vocab Task batches."""
    op.drop_column("tasks", "vocab_batch_fixed_at")
    op.drop_index(op.f("ix_vocab_task_items_vocab_item_id"), table_name="vocab_task_items")
    op.drop_table("vocab_task_items")
    op.drop_index("ix_reviews_event_id_vocab_item_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(op.f("ix_review_states_vocab_item_id"), table_name="review_states")
    op.drop_index("ix_review_states_event_id_due_on", table_name="review_states")
    op.drop_table("review_states")
