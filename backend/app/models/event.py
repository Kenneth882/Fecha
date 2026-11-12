"""An Event and its Plan versions, each a schedule of Milestones and their Tasks."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.services.catalog import EventType
from app.services.planner import Level, TaskKind


def _str_enum(enum: type[StrEnum], name: str) -> Enum:
    """A StrEnum stored as its values in a VARCHAR with a CHECK constraint, like `role`."""
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
        length=16,
    )


class Event(Base):
    """The real-world occasion a User is preparing for.

    There's no status column (ADR 0005): whether it's Active or Past is worked out
    from `abandoned_at`, `event_day` and the User's local today.
    """

    __tablename__ = "events"
    __table_args__ = (CheckConstraint("daily_budget IN (15, 30, 45)", name="daily_budget"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[EventType] = mapped_column(_str_enum(EventType, "event_type"))
    # Validated by the API schema; only "es" for now. No DB constraint, like
    # users.native_language, so adding a language needs no migration.
    target_language: Mapped[str] = mapped_column(String(8))
    event_day: Mapped[date] = mapped_column(Date)
    level: Mapped[Level] = mapped_column(_str_enum(Level, "level"))
    daily_budget: Mapped[int] = mapped_column(SmallInteger)
    # Free text kept for personalising content later; the planner doesn't read it.
    goals: Mapped[str | None] = mapped_column(Text)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # From the clock dependency, not the database, so tests can pin it.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    plans: Mapped[list["Plan"]] = relationship(back_populates="event", lazy="raise")


class Plan(Base):
    """One version of an Event's schedule. The Current Plan has the highest version."""

    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("event_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    version: Mapped[int]
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    event: Mapped[Event] = relationship(back_populates="plans", lazy="raise")
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="plan", lazy="raise")


class Milestone(Base):
    """A Scenario scheduled within one Plan version.

    `scenario_slug` refers to the Scenario Catalog, which lives in code (ADR 0003), so
    there's no foreign key and no title column: the title comes from the catalog.
    """

    __tablename__ = "milestones"
    __table_args__ = (UniqueConstraint("plan_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    scenario_slug: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(SmallInteger)
    target_date: Mapped[date] = mapped_column(Date)

    plan: Mapped[Plan] = relationship(back_populates="milestones", lazy="raise")
    tasks: Mapped[list["Task"]] = relationship(back_populates="milestone", lazy="raise")


class Task(Base):
    """One unit of planned practice on a Plan Day (`date`), for one Milestone."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    milestone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    kind: Mapped[TaskKind] = mapped_column(_str_enum(TaskKind, "task_kind"))
    # Orders the Task within its Plan Day, from 1.
    position: Mapped[int] = mapped_column(SmallInteger)
    estimated_minutes: Mapped[int] = mapped_column(SmallInteger)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    milestone: Mapped[Milestone] = relationship(back_populates="tasks", lazy="raise")
