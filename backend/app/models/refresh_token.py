"""Refresh tokens: how a User stays logged in past one access token (ADR 0007)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    """One refresh token, stored only as the SHA-256 hash of its random value.

    Every login starts a family, and every refresh adds the family's next token and
    revokes the one it replaces, so at most one token per family is live. Revoked
    rows are kept: presenting one again is how reuse (theft) is detected.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Hex SHA-256 of the token; the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # One per login; every token rotated from it shares it.
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # From the clock dependency, not the database, so tests can pin them.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # When it was presented to /auth/refresh; null until then.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Idle limit after its creation, never past the family's absolute cap.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The token it was rotated into.
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
