"""An Event and its Plan versions, each a schedule of Milestones and their Tasks."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum
from app.services.catalog import EventType
from app.services.planner import Level, TaskKind


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
    type: Mapped[EventType] = mapped_column(str_enum(EventType, "event_type"))
    # Validated by the API schema; only "es" for now. No DB constraint, like
    # users.native_language, so adding a language needs no migration.
    target_language: Mapped[str] = mapped_column(String(8))
    event_day: Mapped[date] = mapped_column(Date)
    level: Mapped[Level] = mapped_column(str_enum(Level, "level"))
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
    __table_args__ = (
        CheckConstraint(
            "(kind = 'vocab') = (vocab_batch_size IS NOT NULL)", name="vocab_batch_size"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    milestone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    kind: Mapped[TaskKind] = mapped_column(str_enum(TaskKind, "task_kind"))
    # Orders the Task within its Plan Day, from 1.
    position: Mapped[int] = mapped_column(SmallInteger)
    estimated_minutes: Mapped[int] = mapped_column(SmallInteger)
    # How many Vocab Items a Vocab Task teaches, set by the planner (ADR 0006). Required
    # for Vocab Tasks and null for Listen and Speak Tasks, which the check enforces.
    vocab_batch_size: Mapped[int | None] = mapped_column(SmallInteger)
    # When a Vocab Task's batch was chosen, on first open or completion. Set even when
    # the batch is empty (its Scenario had run out), so an empty batch stays fixed too.
    vocab_batch_fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    milestone: Mapped[Milestone] = relationship(back_populates="tasks", lazy="raise")


class VocabTaskItem(Base):
    """One Vocab Item in a Vocab Task's batch, at its place in the batch (from 1).

    Written once, when the batch is fixed, and never changed afterwards.
    """

    __tablename__ = "vocab_task_items"
    __table_args__ = (
        UniqueConstraint("task_id", "vocab_item_id"),
        CheckConstraint("position >= 1", name="position"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    vocab_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vocab_items.id"), index=True)
