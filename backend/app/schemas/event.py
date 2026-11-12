import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.services.catalog import EventType
from app.services.planner import DailyBudget, Level

TargetLanguage = Literal["es"]


class EventState(StrEnum):
    """Where an Event stands on the User's local today (ADR 0005).

    `active` and `event_day` both make it the User's Active Event; `past` means its
    Event Day has gone by or it was abandoned.
    """

    ACTIVE = "active"
    EVENT_DAY = "event_day"
    PAST = "past"


class EventCreate(BaseModel):
    """What a User sends to create an Event. The Event Day must be 3 to 60 days after
    their local today, which the Event service checks."""

    type: EventType
    target_language: TargetLanguage
    event_day: date
    level: Level
    daily_budget: DailyBudget
    goals: Annotated[str, Field(max_length=500)] | None = None


class EventDetail(BaseModel):
    """An Event with its state, countdown and Current Plan version, on local today."""

    id: uuid.UUID
    type: EventType
    target_language: TargetLanguage
    event_day: date
    level: Level
    daily_budget: DailyBudget
    goals: str | None
    abandoned_at: datetime | None
    created_at: datetime
    state: EventState
    # 0 on the Event Day and afterwards.
    days_until_event_day: int
    current_plan_version: int
