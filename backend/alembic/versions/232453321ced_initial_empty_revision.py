"""initial empty revision

Revision ID: 232453321ced
Revises:
Create Date: 2026-11-09 13:06:51.953471

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "232453321ced"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
