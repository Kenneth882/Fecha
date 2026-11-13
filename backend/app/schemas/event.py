import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.services.catalog import Difficulty, EventType
from app.services.planner import DailyBudget, Level, TaskKind
from app.services.task_status import TaskStatus

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


class EventSummary(BaseModel):
    """An Event as listed: what it is, when, and its state on local today."""

    id: uuid.UUID
    type: EventType
    target_language: TargetLanguage
    event_day: date
    abandoned_at: datetime | None
    created_at: datetime
    state: EventState
    # 0 on the Event Day and afterwards.
    days_until_event_day: int


class EventDetail(EventSummary):
    """An Event with its state, countdown and Current Plan version, on local today."""

    level: Level
    daily_budget: DailyBudget
    goals: str | None
    current_plan_version: int


class PlanTask(BaseModel):
    """One Task in a Plan, with its status on the User's local today."""

    id: uuid.UUID
    kind: TaskKind
    # Its place among all the Plan Day's Tasks, across every Milestone, from 1; a
    # Milestone's own Tasks on that day may not start at 1.
    position: int
    estimated_minutes: int
    status: TaskStatus


class PlanDay(BaseModel):
    """A Milestone's Tasks on one Plan Day, in position order."""

    date: date
    tasks: list[PlanTask]


class PlanMilestone(BaseModel):
    """A Scenario scheduled in the Plan. Its title and difficulty come from the Scenario
    Catalog (ADR 0003)."""

    scenario_slug: str
    title: str
    difficulty: Difficulty
    position: int
    target_date: date
    days: list[PlanDay]


class PlanDetail(BaseModel):
    """An Event's Current Plan: its Milestones in order, each with Tasks by Plan Day."""

    version: int
    milestones: list[PlanMilestone]
