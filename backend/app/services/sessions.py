"""Login sessions kept alive by rotating refresh tokens (ADR 0007).

A login starts a session: a family of refresh tokens, of which only the newest is live.
Each refresh swaps it for the next one. Presenting a revoked token again means someone
else holds a copy, so every session of that User ends. "Now" comes in as a parameter,
from the `get_now` clock dependency.
"""

import logging
import uuid
from datetime import datetime

from fastapi import status
from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_expiry,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse

logger = logging.getLogger(__name__)


class InvalidRefreshTokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_refresh_token"
    message = "The refresh token is invalid or expired: log in again"


async def start_session(
    session: AsyncSession, user: User, now: datetime, settings: Settings
) -> TokenResponse:
    """Start a new session for `user`, commit it, and return its first tokens."""
    return await _issue(session, user.id, uuid.uuid4(), now, now, settings)


async def refresh_session(
    session: AsyncSession, token: str, now: datetime, settings: Settings
) -> TokenResponse:
    """Swap a live refresh token for a new access token and the session's next refresh
    token, and revoke the one presented. Commits.

    Raises InvalidRefreshTokenError for an unknown, expired or revoked token. A revoked
    one also revokes every refresh token of its User first, as it's been reused.
    """
    # Locked until the commit, so two refreshes with one token can't both rotate it:
    # the second sees it revoked, as a replayed copy would be.
    current = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(token))
        .with_for_update()
    )
    if current is None:
        raise InvalidRefreshTokenError
    if current.revoked_at is not None:
        await _revoke(session, RefreshToken.user_id == current.user_id, now)
        logger.warning(
            "refresh token reused: every session of the User revoked",
            extra={"user_id": str(current.user_id), "family_id": str(current.family_id)},
        )
        raise InvalidRefreshTokenError
    if current.expires_at <= now:
        raise InvalidRefreshTokenError

    started = await session.scalar(
        select(func.min(RefreshToken.created_at)).where(RefreshToken.family_id == current.family_id)
    )
    assert started is not None  # the family holds at least `current`
    current.last_used_at = now
    current.revoked_at = now
    return await _issue(
        session, current.user_id, current.family_id, started, now, settings, current
    )


async def end_session(session: AsyncSession, user: User, token: str, now: datetime) -> None:
    """Revoke the session `token` belongs to, if it's one of `user`'s, and commit.

    Any token of the session will do, even one already rotated. Unknown tokens and
    other Users' tokens are ignored, so logging out twice is harmless.
    """
    family_id = await session.scalar(
        select(RefreshToken.family_id).where(
            RefreshToken.token_hash == hash_refresh_token(token),
            RefreshToken.user_id == user.id,
        )
    )
    if family_id is not None:
        await _revoke(session, RefreshToken.family_id == family_id, now)


async def _issue(
    session: AsyncSession,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    started: datetime,
    now: datetime,
    settings: Settings,
    replacing: RefreshToken | None = None,
) -> TokenResponse:
    """Add the family's next refresh token, linked from the one it replaces, and commit."""
    raw = new_refresh_token()
    expires_at = refresh_token_expiry(
        now, started, settings.refresh_token_idle, settings.refresh_token_absolute
    )
    issued = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=hash_refresh_token(raw),
        family_id=family_id,
        created_at=now,
        expires_at=expires_at,
    )
    session.add(issued)
    if replacing is not None:
        # Inserted first: the link is a foreign key, and SQLAlchemy would otherwise
        # flush the update before the insert.
        await session.flush()
        replacing.replaced_by_id = issued.id
    await session.commit()
    access = create_access_token(user_id, settings)
    return TokenResponse(
        access_token=access.token,
        expires_in=access.expires_in,
        refresh_token=raw,
        refresh_expires_in=int((expires_at - now).total_seconds()),
    )


async def _revoke(session: AsyncSession, which: ColumnElement[bool], now: datetime) -> None:
    """Revoke every live refresh token matching `which`, and commit."""
    await session.execute(
        update(RefreshToken).where(which, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )
    await session.commit()
