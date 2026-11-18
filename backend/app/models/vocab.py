"""Vocab Items: the phrases, with translations, that Vocab Tasks introduce."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum
from app.services.planner import Level

# Every generated item's key starts with this, and no seed item's key does, so the
# seed loader and generation (Week 4) can never claim the same item_key.
GENERATED_KEY_PREFIX = "gen_"


class VocabSource(StrEnum):
    """Where a Vocab Item came from: the committed seed file, or LLM generation (Week 4)."""

    SEED = "seed"
    GENERATED = "generated"


class VocabItem(Base):
    """A phrase in a target language, with its English translation, for one Scenario.

    Shared across Users. `scenario_slug` refers to the Scenario Catalog in code (ADR
    0003), so there's no foreign key. `item_key` is stable within a Scenario and
    language; generated items' keys start with `GENERATED_KEY_PREFIX` and seed items'
    never do. `position` orders the
    Scenario's items, easiest and most essential first. A retired item stays for the
    Review States that refer to it but is never put in a new batch.
    """

    __tablename__ = "vocab_items"
    __table_args__ = (
        UniqueConstraint("scenario_slug", "language", "item_key"),
        CheckConstraint("position >= 1", name="position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scenario_slug: Mapped[str] = mapped_column(String(64))
    # No DB constraint, like events.target_language, so adding a language needs no
    # migration.
    language: Mapped[str] = mapped_column(String(8))
    # Null means the item suits every Level.
    level: Mapped[Level | None] = mapped_column(str_enum(Level, "level"))
    item_key: Mapped[str] = mapped_column(String(64))
    phrase: Mapped[str] = mapped_column(Text)
    translation: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[VocabSource] = mapped_column(str_enum(VocabSource, "vocab_source"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
