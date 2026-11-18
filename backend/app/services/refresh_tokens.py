"""Rotating refresh tokens, which keep a User logged in past one access token (ADR 0007).

Each login starts a family of refresh tokens, of which only the newest is live: every
refresh swaps it for the next one. Presenting a revoked token again means someone else
holds a copy, so every token of that User is revoked. The exceptions: an expired token
is simply refused, and a token swapped by a refresh within the last
`refresh_token_reuse_grace` (a race between two tabs, or a retry) gets a token of its
own, as long as its family hasn't been logged out. "Now" comes in as a parameter, from
the `get_now` clock dependency.
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


async def issue_for_login(
    session: AsyncSession, user: User, now: datetime, settings: Settings
) -> TokenResponse:
    """Start a new family for `user`, commit it, and return its first tokens."""
    issued, raw = _next_token(user.id, uuid.uuid4(), now, now, settings)
    session.add(issued)
    await session.commit()
    return _tokens(issued, raw, now, settings)


async def rotate(
    session: AsyncSession, token: str, now: datetime, settings: Settings
) -> TokenResponse:
    """Swap a live refresh token for a new access token and its family's next refresh
    token, and revoke the one presented. Commits.

    Raises InvalidRefreshTokenError for an unknown, expired or revoked token. A revoked
    one has been reused, so every refresh token of its User is revoked first, unless a
    refresh swapped it within the grace period: then, if its family is still live, it
    gets a new token of its own, and if not, it's just refused.
    """
    # Locked until the commit, so two refreshes with one token can't both rotate it:
    # the second sees it revoked and falls into the grace period.
    current = await session.scalar(select(RefreshToken).where(_matches(token)).with_for_update())
    if current is None:
        raise InvalidRefreshTokenError
    # Expiry first: an expired token can't refresh anything, so replaying one isn't
    # worth ending every session over.
    if current.expires_at <= now:
        raise InvalidRefreshTokenError
    log = {"user_id": str(current.user_id), "family_id": str(current.family_id)}
    if current.revoked_at is not None:
        if not _swapped_within_grace(current, now, settings):
            await _revoke(session, RefreshToken.user_id == current.user_id, now)
            logger.warning(
                "refresh token reused: every refresh token of the User revoked", extra=log
            )
            raise InvalidRefreshTokenError
        if not await _family_is_live(session, current.family_id):
            # Lost a race with logout (or theft detection), not a sign of theft itself.
            raise InvalidRefreshTokenError
        logger.info("refresh token reused within the grace period", extra=log)

    family_started = await session.scalar(
        select(func.min(RefreshToken.created_at)).where(RefreshToken.family_id == current.family_id)
    )
    assert family_started is not None  # the family holds at least `current`
    issued, raw = _next_token(current.user_id, current.family_id, family_started, now, settings)
    session.add(issued)
    if current.revoked_at is None:
        # Inserted before `current` links to it: the link is a foreign key, and
        # SQLAlchemy would otherwise flush the update first. A grace-period reuse keeps
        # the link to the token its first refresh issued.
        await session.flush()
        current.last_used_at = now
        current.revoked_at = now
        current.replaced_by_id = issued.id
    await session.commit()
    return _tokens(issued, raw, now, settings)


async def revoke_family(session: AsyncSession, user: User, token: str, now: datetime) -> None:
    """Revoke the family `token` belongs to, if it's one of `user`'s, and commit.

    Any token of the family will do, even one already rotated. Unknown tokens and
    other Users' tokens are ignored, so logging out twice is harmless.
    """
    family_id = await session.scalar(
        select(RefreshToken.family_id).where(_matches(token), RefreshToken.user_id == user.id)
    )
    if family_id is not None:
        await _revoke(session, RefreshToken.family_id == family_id, now)


def _swapped_within_grace(token: RefreshToken, now: datetime, settings: Settings) -> bool:
    """Whether a refresh, not a logout or theft, revoked `token` within the grace period."""
    return (
        token.replaced_by_id is not None
        and token.revoked_at is not None
        and now - token.revoked_at < settings.refresh_token_reuse_grace
    )


async def _family_is_live(session: AsyncSession, family_id: uuid.UUID) -> bool:
    """Whether the family still has an unrevoked token: false once it's logged out."""
    live = await session.scalar(
        select(RefreshToken.id)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .limit(1)
    )
    return live is not None


def _matches(token: str) -> ColumnElement[bool]:
    """The stored row for `token`, found by its hash."""
    return RefreshToken.token_hash == hash_refresh_token(token)


def _next_token(
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    family_started: datetime,
    now: datetime,
    settings: Settings,
) -> tuple[RefreshToken, str]:
    """A new refresh token row for the family, and the raw token, which isn't stored."""
    raw = new_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw),
        family_id=family_id,
        created_at=now,
        expires_at=refresh_token_expiry(
            now, family_started, settings.refresh_token_idle, settings.refresh_token_absolute
        ),
    )
    return row, raw


def _tokens(issued: RefreshToken, raw: str, now: datetime, settings: Settings) -> TokenResponse:
    """The response for a newly issued refresh token, with a fresh access token."""
    access = create_access_token(issued.user_id, settings)
    return TokenResponse(
        access_token=access.token,
        expires_in=access.expires_in,
        refresh_token=raw,
        refresh_expires_in=int((issued.expires_at - now).total_seconds()),
    )


async def _revoke(session: AsyncSession, which: ColumnElement[bool], now: datetime) -> None:
    """Revoke every live refresh token matching `which`, and commit."""
    await session.execute(
        update(RefreshToken).where(which, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )
    await session.commit()
