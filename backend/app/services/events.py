"""Creating and reading a User's Events, each with its Plan versions.

"Now" always comes in as a parameter, from the `get_now` clock dependency, and is turned
into the User's local today here. Event states are derived, never stored (ADR 0005).
"""

import uuid
from datetime import date, datetime
from itertools import groupby
from typing import cast

from fastapi import status
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models.event import Event, Milestone, Plan, Task
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventDetail,
    EventState,
    EventSummary,
    PlanDay,
    PlanDetail,
    PlanMilestone,
    PlanTask,
    TargetLanguage,
)
from app.services.catalog import find_scenario
from app.services.local_time import local_today
from app.services.planner import MIN_PLAN_DAYS, DailyBudget, DraftPlan, build_plan
from app.services.task_status import task_status

# A cram planner, not a general course.
MAX_DAYS_AHEAD = 60


class EventDayOutOfRangeError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "event_day_out_of_range"
    message = (
        f"The Event Day must be {MIN_PLAN_DAYS} to {MAX_DAYS_AHEAD} days after your local today"
    )


class ActiveEventExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "active_event_exists"
    message = "You already have an Active Event: abandon it before creating another"


class EventAlreadyPastError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "event_already_past"
    message = "This Event is already past: it was abandoned or its Event Day has gone by"


class EventNotFoundError(AppError):
    # The same for another User's Event as for an unknown ID, so IDs can't be probed.
    status_code = status.HTTP_404_NOT_FOUND
    code = "event_not_found"
    message = "No such Event"


async def create_event(
    session: AsyncSession, user: User, data: EventCreate, now: datetime
) -> EventDetail:
    """Create and commit an Event with its first Plan, built by the planner from the
    User's local today (ADR 0004).

    Raises EventDayOutOfRangeError unless the Event Day is 3 to 60 of the User's local
    days after their local today, and ActiveEventExistsError if the User already
    has an Active Event (ADR 0001). The User's row stays locked from that check until
    the commit, so two simultaneous creates can't both pass it (ADR 0005).
    """
    today = local_today(now, user.timezone)
    if not MIN_PLAN_DAYS <= (data.event_day - today).days <= MAX_DAYS_AHEAD:
        raise EventDayOutOfRangeError
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    if await _has_active_event(session, user, today):
        raise ActiveEventExistsError
    draft = build_plan(
        event_type=data.type,
        level=data.level,
        daily_budget=data.daily_budget,
        start_date=today,
        event_day=data.event_day,
    )
    event = Event(
        user_id=user.id,
        type=data.type,
        target_language=data.target_language,
        event_day=data.event_day,
        level=data.level,
        daily_budget=data.daily_budget,
        goals=data.goals,
        created_at=now,
    )
    plan = _plan_rows(event, draft, version=1, generated_at=now)
    session.add_all([event, plan])
    await session.commit()
    return _detail(event, plan.version, today)


async def get_event(
    session: AsyncSession, user: User, event_id: uuid.UUID, now: datetime
) -> EventDetail:
    """One of the User's Events, on their local today.

    Raises EventNotFoundError if there's no such Event or it belongs to another User.
    """
    event, version = await _own_event(session, user, event_id)
    return _detail(event, version, local_today(now, user.timezone))


async def abandon_event(
    session: AsyncSession, user: User, event_id: uuid.UUID, now: datetime
) -> EventDetail:
    """Abandon the User's Active Event at `now`, so they can create another (ADR 0001).

    Raises EventNotFoundError as `get_event` does, and EventAlreadyPastError if the
    Event was already abandoned or its Event Day has gone by. The Event's row is
    locked from the check until the commit, so it's abandoned only once.
    """
    event, version = await _own_event(session, user, event_id, for_update=True)
    today = local_today(now, user.timezone)
    if event_state(event, today) is EventState.PAST:
        raise EventAlreadyPastError
    event.abandoned_at = now
    await session.commit()
    return _detail(event, version, today)


async def list_events(session: AsyncSession, user: User, now: datetime) -> list[EventSummary]:
    """All the User's Events, newest first, each with its state on their local today."""
    today = local_today(now, user.timezone)
    rows = await session.scalars(
        select(Event)
        .where(Event.user_id == user.id)
        .order_by(Event.created_at.desc(), Event.id.desc())
    )
    return [_summary(event, today) for event in rows]


async def get_current_plan(
    session: AsyncSession, user: User, event_id: uuid.UUID, now: datetime
) -> PlanDetail:
    """The Current Plan of one of the User's Events, with each Task's status on their
    local today. Superseded Plans aren't exposed.

    Raises EventNotFoundError as `get_event` does.
    """
    event, version = await _own_event(session, user, event_id)
    plan = await session.scalar(
        select(Plan)
        .where(Plan.event_id == event.id, Plan.version == version)
        .options(selectinload(Plan.milestones).selectinload(Milestone.tasks))
    )
    # Every Event is created with its first Plan in the same transaction (ADR 0004).
    assert plan is not None
    today = local_today(now, user.timezone)
    return PlanDetail(
        version=plan.version,
        milestones=[
            _plan_milestone(m, today) for m in sorted(plan.milestones, key=lambda m: m.position)
        ],
    )


async def _own_event(
    session: AsyncSession, user: User, event_id: uuid.UUID, *, for_update: bool = False
) -> tuple[Event, int]:
    """One of the User's Events and its Current Plan version.

    Raises EventNotFoundError if there's no such Event or it belongs to another User.
    """
    current_version = (
        select(func.max(Plan.version)).where(Plan.event_id == Event.id).scalar_subquery()
    )
    query = select(Event, current_version).where(Event.id == event_id, Event.user_id == user.id)
    if for_update:
        query = query.with_for_update(of=Event)
    row = (await session.execute(query)).one_or_none()
    if row is None:
        raise EventNotFoundError
    event, version = row
    return event, version


async def _has_active_event(session: AsyncSession, user: User, today: date) -> bool:
    """Whether one of the User's Events is `active` or `event_day` on `today`: the
    database form of `event_state`."""
    active = exists().where(
        Event.user_id == user.id, Event.abandoned_at.is_(None), Event.event_day >= today
    )
    return bool(await session.scalar(select(active)))


def _plan_rows(event: Event, draft: DraftPlan, *, version: int, generated_at: datetime) -> Plan:
    """The rows for storing `draft` as `event`'s Plan `version`."""
    return Plan(
        event=event,
        version=version,
        generated_at=generated_at,
        milestones=[
            Milestone(
                scenario_slug=m.scenario_slug,
                position=m.position,
                target_date=m.target_date,
                tasks=[
                    Task(
                        date=t.date,
                        kind=t.kind,
                        position=t.position,
                        estimated_minutes=t.estimated_minutes,
                    )
                    for t in m.tasks
                ],
            )
            for m in draft.milestones
        ],
    )


def _plan_milestone(milestone: Milestone, today: date) -> PlanMilestone:
    """`milestone` with its Scenario's catalog details and its Tasks grouped by Plan
    Day, each with its status on `today`."""
    scenario = find_scenario(milestone.scenario_slug)
    if scenario is None:
        # Stored slugs always name a catalog Scenario (ADR 0003); a test guards it.
        raise LookupError(f"Scenario {milestone.scenario_slug!r} isn't in the catalog")
    tasks = sorted(milestone.tasks, key=lambda t: (t.date, t.position))
    return PlanMilestone(
        scenario_slug=scenario.slug,
        title=scenario.title,
        difficulty=scenario.difficulty,
        position=milestone.position,
        target_date=milestone.target_date,
        days=[
            PlanDay(date=day, tasks=[_plan_task(t, today) for t in day_tasks])
            for day, day_tasks in groupby(tasks, key=lambda t: t.date)
        ],
    )


def _plan_task(task: Task, today: date) -> PlanTask:
    return PlanTask(
        id=task.id,
        kind=task.kind,
        position=task.position,
        estimated_minutes=task.estimated_minutes,
        status=task_status(task.date, task.completed_at, today=today),
    )


def event_state(event: Event, today: date) -> EventState:
    """`past` once abandoned or after the Event Day, `event_day` on it, else `active`."""
    if event.abandoned_at is not None or today > event.event_day:
        return EventState.PAST
    if today == event.event_day:
        return EventState.EVENT_DAY
    return EventState.ACTIVE


def _summary(event: Event, today: date) -> EventSummary:
    return EventSummary(
        id=event.id,
        type=event.type,
        # The columns hold only what EventCreate accepted.
        target_language=cast(TargetLanguage, event.target_language),
        event_day=event.event_day,
        abandoned_at=event.abandoned_at,
        created_at=event.created_at,
        state=event_state(event, today),
        days_until_event_day=max((event.event_day - today).days, 0),
    )


def _detail(event: Event, plan_version: int, today: date) -> EventDetail:
    return EventDetail(
        **_summary(event, today).model_dump(),
        level=event.level,
        # The column holds only what EventCreate accepted.
        daily_budget=cast(DailyBudget, event.daily_budget),
        goals=event.goals,
        current_plan_version=plan_version,
    )
