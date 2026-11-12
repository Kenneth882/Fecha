"""create events, plans, milestones and tasks

Revision ID: 28e76244ce4b
Revises: 37937351216b
Create Date: 2026-11-12 15:50:44.861718

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "28e76244ce4b"
down_revision: str | Sequence[str] | None = "37937351216b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the events, plans, milestones and tasks tables."""
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "interview",
                "relocation",
                "speech",
                name="event_type",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("target_language", sa.String(length=8), nullable=False),
        sa.Column("event_day", sa.Date(), nullable=False),
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
            nullable=False,
        ),
        sa.Column("daily_budget", sa.SmallInteger(), nullable=False),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("daily_budget IN (15, 30, 45)", name=op.f("ck_events_daily_budget")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_events_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index(op.f("ix_events_user_id"), "events", ["user_id"], unique=False)
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_plans_event_id_events"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
        sa.UniqueConstraint("event_id", "version", name=op.f("uq_plans_event_id")),
    )
    op.create_table(
        "milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_slug", sa.String(length=64), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_milestones_plan_id_plans"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_milestones")),
        sa.UniqueConstraint("plan_id", "position", name=op.f("uq_milestones_plan_id")),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("milestone_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "vocab",
                "listen",
                "speak",
                name="task_kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["milestones.id"],
            name=op.f("fk_tasks_milestone_id_milestones"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_milestone_id"), "tasks", ["milestone_id"], unique=False)


def downgrade() -> None:
    """Drop the events, plans, milestones and tasks tables."""
    op.drop_index(op.f("ix_tasks_milestone_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("milestones")
    op.drop_table("plans")
    op.drop_index(op.f("ix_events_user_id"), table_name="events")
    op.drop_table("events")
