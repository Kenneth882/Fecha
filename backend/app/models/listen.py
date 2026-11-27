"""Listen Dialogues, and the User's answers to a Listen Task's Comprehension Questions."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    and_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum
from app.services.listen_content import ListenDialogueContent
from app.services.planner import Level


class ListenSource(StrEnum):
    """Where a Listen Dialogue came from: the hand-written fallback file, or LLM
    generation (#69)."""

    FALLBACK = "fallback"
    GENERATED = "generated"


class ListenDialogue(Base):
    """A short conversation in one Scenario and target language, with three
    Comprehension Questions. Shared across Users.

    Never edited in place, because Listen Tasks and their answers refer to it: a bad or
    changed one is retired instead. A fallback has no Level, since it suits every Level;
    a generated one always has one. Each Scenario and language has at most one live
    (unretired) fallback. `speakers`, `lines` and `questions` hold a
    `ListenDialogueContent`, which `content()` reads back.
    """

    __tablename__ = "listen_dialogues"
    __table_args__ = (
        CheckConstraint("(source = 'fallback') = (level IS NULL)", name="fallback_level"),
        Index(
            "uq_listen_dialogues_live_fallback",
            "scenario_slug",
            "language",
            unique=True,
            postgresql_where=text("source = 'fallback' AND retired_at IS NULL"),
        ),
        Index("ix_listen_dialogues_key", "scenario_slug", "language", "level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # The Scenario Catalog lives in code (ADR 0003), so there's no foreign key.
    scenario_slug: Mapped[str] = mapped_column(String(64))
    # No DB constraint, like vocab_items.language, so adding a language needs no migration.
    language: Mapped[str] = mapped_column(String(8))
    level: Mapped[Level | None] = mapped_column(str_enum(Level, "level"))
    source: Mapped[ListenSource] = mapped_column(str_enum(ListenSource, "listen_source"))
    speakers: Mapped[list[str]] = mapped_column(JSONB)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @classmethod
    def live_fallback(cls, language: str) -> ColumnElement[bool]:
        """The condition for a live (unretired) hand-written fallback in `language`."""
        return and_(
            cls.language == language,
            cls.source == ListenSource.FALLBACK,
            cls.retired_at.is_(None),
        )

    @classmethod
    def live_generated(cls, scenario_slug: str, language: str, level: Level) -> ColumnElement[bool]:
        """The condition for the live generated pool of a (language, Scenario, Level) key."""
        return and_(
            cls.scenario_slug == scenario_slug,
            cls.language == language,
            cls.level == level,
            cls.source == ListenSource.GENERATED,
            cls.retired_at.is_(None),
        )

    @classmethod
    def from_content(cls, content: ListenDialogueContent, **columns: Any) -> "ListenDialogue":
        """A new row holding `content`, with the other `columns` set."""
        stored = content.model_dump(mode="json")
        return cls(
            speakers=stored["speakers"],
            lines=stored["lines"],
            questions=stored["questions"],
            **columns,
        )

    def content(self) -> ListenDialogueContent:
        """The dialogue and its questions, as validated when they were stored."""
        return ListenDialogueContent.model_validate(
            {"speakers": self.speakers, "lines": self.lines, "questions": self.questions}
        )


class ListenAnswer(Base):
    """The User's one answer to one Comprehension Question of a Listen Task.

    Written once and never changed: an answer is final. `question` and `choice` count
    from 1, like a Listen Dialogue's options.
    """

    __tablename__ = "listen_answers"
    __table_args__ = (
        CheckConstraint("question BETWEEN 1 AND 3", name="question"),
        CheckConstraint("choice BETWEEN 1 AND 3", name="choice"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    question: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    choice: Mapped[int] = mapped_column(SmallInteger)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
