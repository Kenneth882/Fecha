"""add listen dialogues and listen answers

Revision ID: a82fef7f2f5a
Revises: c26e6e3188c8
Create Date: 2026-11-26 18:46:32.907765

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a82fef7f2f5a"
down_revision: str | Sequence[str] | None = "c26e6e3188c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Listen Dialogues and Listen answers, and give Listen Tasks a fixed
    Listen Dialogue (#67).

    Existing Listen Tasks keep a null `listen_dialogue_id`: their dialogue is chosen the
    first time they're opened or answered.
    """
    op.create_table(
        "listen_dialogues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_slug", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "A1",
                "A2",
                "B1",
                "B2",
                "C1",
                name="level",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "fallback",
                "generated",
                name="listen_source",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("speakers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(source = 'fallback') = (level IS NULL)",
            name=op.f("ck_listen_dialogues_fallback_level"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listen_dialogues")),
    )
    op.create_index(
        "ix_listen_dialogues_key",
        "listen_dialogues",
        ["scenario_slug", "language", "level"],
        unique=False,
    )
    op.create_index(
        "uq_listen_dialogues_live_fallback",
        "listen_dialogues",
        ["scenario_slug", "language"],
        unique=True,
        postgresql_where=sa.text("source = 'fallback' AND retired_at IS NULL"),
    )
    op.create_table(
        "listen_answers",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.SmallInteger(), nullable=False),
        sa.Column("choice", sa.SmallInteger(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("choice BETWEEN 1 AND 3", name=op.f("ck_listen_answers_choice")),
        sa.CheckConstraint("question BETWEEN 1 AND 3", name=op.f("ck_listen_answers_question")),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_listen_answers_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", "question", name=op.f("pk_listen_answers")),
    )
    op.add_column("tasks", sa.Column("listen_dialogue_id", sa.Uuid(), nullable=True))
    op.add_column(
        "tasks", sa.Column("listen_dialogue_fixed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        op.f("ix_tasks_listen_dialogue_id"), "tasks", ["listen_dialogue_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_tasks_listen_dialogue_id_listen_dialogues"),
        "tasks",
        "listen_dialogues",
        ["listen_dialogue_id"],
        ["id"],
    )
    # Autogenerate doesn't see check constraints added to an existing table.
    op.create_check_constraint(
        op.f("ck_tasks_listen_dialogue_kind"),
        "tasks",
        "listen_dialogue_id IS NULL OR kind = 'listen'",
    )
    op.create_check_constraint(
        op.f("ck_tasks_listen_dialogue_fixed_at"),
        "tasks",
        "(listen_dialogue_id IS NULL) = (listen_dialogue_fixed_at IS NULL)",
    )


def downgrade() -> None:
    """Drop Listen Dialogues and answers, and Listen Tasks' fixed dialogues."""
    op.drop_constraint(op.f("ck_tasks_listen_dialogue_fixed_at"), "tasks", type_="check")
    op.drop_constraint(op.f("ck_tasks_listen_dialogue_kind"), "tasks", type_="check")
    op.drop_constraint(
        op.f("fk_tasks_listen_dialogue_id_listen_dialogues"), "tasks", type_="foreignkey"
    )
    op.drop_index(op.f("ix_tasks_listen_dialogue_id"), table_name="tasks")
    op.drop_column("tasks", "listen_dialogue_fixed_at")
    op.drop_column("tasks", "listen_dialogue_id")
    op.drop_table("listen_answers")
    op.drop_index(
        "uq_listen_dialogues_live_fallback",
        table_name="listen_dialogues",
        postgresql_where=sa.text("source = 'fallback' AND retired_at IS NULL"),
    )
    op.drop_index("ix_listen_dialogues_key", table_name="listen_dialogues")
    op.drop_table("listen_dialogues")
