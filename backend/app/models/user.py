import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """A person preparing for an Event."""

    __tablename__ = "users"
    # Load server-generated columns (created_at) with RETURNING on insert.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Always stored lowercased, so the unique constraint ignores letter case.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Validated by the API schema; only "en" for now. No DB constraint, so adding a
    # language needs no migration.
    native_language: Mapped[str] = mapped_column(String(8))
    # An IANA name, validated by the API schema.
    timezone: Mapped[str] = mapped_column(String(64))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda roles: [role.value for role in roles],
            length=16,
        ),
        default=Role.USER,
        server_default=Role.USER.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
