"""One row per attempt to generate content through the content generator."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum
from app.services.planner import Level


class ContentKind(StrEnum):
    """What a call was asked to generate."""

    LISTEN_DIALOGUE = "listen_dialogue"
    VOCAB_ITEMS = "vocab_items"


class LlmOutcome(StrEnum):
    """How an attempt ended: content stored, a failure (so Users get the fallback), or
    no call made because there's no API key or the day's budget is spent."""

    GENERATED = "generated"
    FALLBACK_AFTER_FAILURE = "fallback_after_failure"
    SKIPPED_NO_KEY = "skipped_no_key"
    SKIPPED_CAP = "skipped_cap"


class LlmCall(Base):
    """One attempt to generate one piece of content for a (language, Scenario, Level)
    key, with what it cost. Written once; the daily budget and Week 8's admin metrics
    read it.

    A skipped attempt made no call, so it has no model or latency, and costs nothing.
    """

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_kind: Mapped[ContentKind] = mapped_column(str_enum(ContentKind, "content_kind"))
    # The Scenario Catalog lives in code (ADR 0003), so there's no foreign key.
    scenario_slug: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(8))
    level: Mapped[Level] = mapped_column(str_enum(Level, "level"))
    model: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal(0))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[LlmOutcome] = mapped_column(str_enum(LlmOutcome, "llm_outcome", length=32))
    # Indexed: the daily budget sums the day's costs before every call.
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
