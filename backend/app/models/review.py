"""Spaced repetition per Event: each Introduced Vocab Item's Review State, and the
append-only log of Reviews."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReviewState(Base):
    """The spaced-repetition progress of one Introduced Vocab Item within one Event.

    Keyed by (Event, Vocab Item), so each Event starts fresh (ADR 0001). The columns
    mirror `services.srs.ReviewState`, which computes them. `due_on` is null once
    nothing more is scheduled before the Event Day.
    """

    __tablename__ = "review_states"
    __table_args__ = (Index("ix_review_states_event_id_due_on", "event_id", "due_on"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    vocab_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocab_items.id"), primary_key=True, index=True
    )
    introduced_on: Mapped[date] = mapped_column(Date)
    ease: Mapped[float] = mapped_column(Float)
    interval_days: Mapped[int] = mapped_column(SmallInteger)
    repetitions: Mapped[int] = mapped_column(SmallInteger)
    lapses: Mapped[int] = mapped_column(SmallInteger)
    due_on: Mapped[date | None] = mapped_column(Date)
    reviewed_in_final_window: Mapped[bool]


class Review(Base):
    """One graded recall of an Introduced Vocab Item. Append-only: rows are never
    updated or deleted. `plan_day` is the User's local date it was given on."""

    __tablename__ = "reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "vocab_item_id"],
            ["review_states.event_id", "review_states.vocab_item_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("grade BETWEEN 0 AND 5", name="grade"),
        Index("ix_reviews_event_id_vocab_item_id", "event_id", "vocab_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column()
    vocab_item_id: Mapped[uuid.UUID] = mapped_column()
    plan_day: Mapped[date] = mapped_column(Date)
    grade: Mapped[int] = mapped_column(SmallInteger)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
