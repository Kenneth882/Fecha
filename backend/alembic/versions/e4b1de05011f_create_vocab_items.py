"""create vocab_items

Revision ID: e4b1de05011f
Revises: 28e76244ce4b
Create Date: 2026-11-18 14:28:25.775572

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b1de05011f"
down_revision: str | Sequence[str] | None = "28e76244ce4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the vocab_items table. The seed rows are loaded by `app.load_seed_vocab`."""
    op.create_table(
        "vocab_items",
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
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "seed",
                "generated",
                name="vocab_source",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("position >= 1", name=op.f("ck_vocab_items_position")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vocab_items")),
        sa.UniqueConstraint(
            "scenario_slug", "language", "item_key", name=op.f("uq_vocab_items_scenario_slug")
        ),
    )


def downgrade() -> None:
    """Drop the vocab_items table."""
    op.drop_table("vocab_items")
