"""add llm calls

Revision ID: 4bec2e651167
Revises: a82fef7f2f5a
Create Date: 2026-11-26 19:11:45.048071

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4bec2e651167"
down_revision: str | Sequence[str] | None = "a82fef7f2f5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the LLM calls table: one row per content generation attempt (#69)."""
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "content_kind",
            sa.Enum(
                "listen_dialogue",
                "vocab_items",
                name="content_kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
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
            nullable=False,
        ),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "generated",
                "fallback_after_failure",
                "skipped_no_key",
                "skipped_cap",
                name="llm_outcome",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_calls")),
    )
    op.create_index(op.f("ix_llm_calls_called_at"), "llm_calls", ["called_at"], unique=False)


def downgrade() -> None:
    """Drop the LLM calls table."""
    op.drop_index(op.f("ix_llm_calls_called_at"), table_name="llm_calls")
    op.drop_table("llm_calls")
