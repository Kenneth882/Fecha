import asyncio

from fastapi import status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate

# Named by the convention in models/base.py; see the users migration.
EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"


class EmailTakenError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "email_taken"
    message = "This email is already registered"


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    """Create and commit a new User. `data.email` is already lowercased.

    Raises EmailTakenError if the email is in use. The unique constraint decides,
    not a lookup first, so two simultaneous registrations can't both succeed.
    """
    user = User(
        email=data.email,
        # argon2 is deliberately slow; keep it off the event loop.
        password_hash=await asyncio.to_thread(hash_password, data.password),
        timezone=data.timezone,
        native_language=data.native_language,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # asyncpg's UniqueViolationError, wrapped by SQLAlchemy's driver adapter.
        cause = exc.orig.__cause__ if exc.orig is not None else None
        if getattr(cause, "constraint_name", None) == EMAIL_UNIQUE_CONSTRAINT:
            raise EmailTakenError from None
        raise
    return user


async def delete_user_by_email(session: AsyncSession, email: str) -> None:
    """Delete the User with this (lowercased) email, if any, without committing.

    A bulk delete, so the database's ON DELETE CASCADE removes their Events, Plans
    and Tasks too.
    """
    await session.execute(delete(User).where(User.email == email))
