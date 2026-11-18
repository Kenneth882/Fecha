"""Opening and completing a User's Tasks. Only Vocab Tasks can be done so far.

A Vocab Task's batch is fixed the first time it's opened or completed, and stored in
`vocab_task_items`. Completing the Task introduces the batch: one Review State per item,
from `srs.introduce`.
"""

import uuid
from datetime import date, datetime

from fastapi import status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.event import Event, Milestone, Plan, Task, VocabTaskItem
from app.models.review import ReviewState
from app.models.user import User
from app.models.vocab import VocabItem
from app.schemas.event import EventState
from app.schemas.task import TaskCompletion, VocabBatch, VocabBatchItem
from app.services import srs
from app.services.events import EventAlreadyPastError, event_state
from app.services.local_time import local_today
from app.services.planner import TaskKind
from app.services.task_status import TaskStatus, task_status


class TaskNotFoundError(AppError):
    # The same for another User's Task as for an unknown ID, so IDs can't be probed.
    status_code = status.HTTP_404_NOT_FOUND
    code = "task_not_found"
    message = "No such Task"


class NotAVocabTaskError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "not_a_vocab_task"
    message = "Only Vocab Tasks can be opened or completed for now"


class TaskMissedError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "task_missed"
    message = "This Task was missed: its Plan Day has ended, so it can't be completed"


async def open_vocab_task(
    session: AsyncSession, user: User, task_id: uuid.UUID, now: datetime
) -> VocabBatch:
    """One of the User's Vocab Tasks' batch, fixing it if this is the first open.

    Introduces nothing. A Task that can no longer be completed (Missed, or a Past
    Event's) is read-only: it shows the batch fixed before, or none. Raises
    TaskNotFoundError if there's no such Task or it's another User's, and
    NotAVocabTaskError for a Listen or Speak Task.
    """
    task, event, scenario_slug = await _own_vocab_task(session, user, task_id)
    if task.vocab_batch_fixed_at is None:
        await _lock_event(session, event, task)
        today = local_today(now, user.timezone)
        if task.vocab_batch_fixed_at is None and _can_complete(task, event, today):
            await _fix_batch(session, task, event, scenario_slug, today, now)
            await session.commit()
    items = await _fixed_batch_items(session, task)
    return VocabBatch(
        task_id=task.id,
        items=[VocabBatchItem(id=i.id, phrase=i.phrase, translation=i.translation) for i in items],
    )


async def complete_task(
    session: AsyncSession, user: User, task_id: uuid.UUID, now: datetime
) -> TaskCompletion:
    """Complete one of the User's Vocab Tasks at `now`, introducing its batch.

    Fixes the batch if it wasn't fixed yet, and gives each item a Review State from
    `srs.introduce`, first due the next day. Idempotent: completing it again changes
    nothing and returns the same answer, even once the Event is past. Raises
    TaskNotFoundError and NotAVocabTaskError as `open_vocab_task` does,
    EventAlreadyPastError for a Past Event's Task, and TaskMissedError for a Missed
    Task.
    """
    task, event, scenario_slug = await _own_vocab_task(session, user, task_id)
    await _lock_event(session, event, task)
    if task.completed_at is not None:
        # A batch's items are introduced only by its own Task (see `_fix_batch`).
        items = await _fixed_batch_items(session, task)
        return TaskCompletion(
            task_id=task.id, status=TaskStatus.COMPLETED, items_introduced=len(items)
        )
    today = local_today(now, user.timezone)
    if event_state(event, today) is EventState.PAST:
        raise EventAlreadyPastError
    if task_status(task.date, task.completed_at, today=today) is TaskStatus.MISSED:
        raise TaskMissedError
    if task.vocab_batch_fixed_at is None:
        await _fix_batch(session, task, event, scenario_slug, today, now)
        await session.flush()
    items = await _fixed_batch_items(session, task)
    session.add_all(
        ReviewState(
            event_id=event.id,
            vocab_item_id=item.id,
            **srs.introduce(item.id, introduced_on=today, event_day=event.event_day).model_dump(),
        )
        for item in items
    )
    task.completed_at = now
    await session.commit()
    return TaskCompletion(task_id=task.id, status=TaskStatus.COMPLETED, items_introduced=len(items))


def _can_complete(task: Task, event: Event, today: date) -> bool:
    """Whether `task` could still be completed on `today`: not Missed, and its Event
    not past."""
    return (
        event_state(event, today) is not EventState.PAST
        and task_status(task.date, task.completed_at, today=today) is not TaskStatus.MISSED
    )


async def _own_vocab_task(
    session: AsyncSession, user: User, task_id: uuid.UUID
) -> tuple[Task, Event, str]:
    """One of the User's Vocab Tasks, its Event and its Milestone's Scenario slug."""
    row = (
        await session.execute(
            select(Task, Event, Milestone.scenario_slug)
            .join(Milestone, Task.milestone_id == Milestone.id)
            .join(Plan, Milestone.plan_id == Plan.id)
            .join(Event, Plan.event_id == Event.id)
            .where(Task.id == task_id, Event.user_id == user.id)
        )
    ).one_or_none()
    if row is None:
        raise TaskNotFoundError
    task, event, scenario_slug = row
    if task.kind is not TaskKind.VOCAB:
        raise NotAVocabTaskError
    return task, event, scenario_slug


async def _lock_event(session: AsyncSession, event: Event, task: Task) -> None:
    """Lock the Event's row until the commit, then reload `task`.

    Every batch fix and completion for an Event takes this lock first, so two requests
    can't fix the same items into two batches, fix one batch twice, or complete a Task
    twice. `task` is reloaded because another request may have changed it meanwhile.
    """
    await session.execute(
        select(Event)
        .where(Event.id == event.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    await session.refresh(task)


async def _fixed_batch_items(session: AsyncSession, task: Task) -> list[VocabItem]:
    """The Task's fixed batch, in order: empty if it isn't fixed yet."""
    rows = await session.scalars(
        select(VocabItem)
        .join(VocabTaskItem, VocabTaskItem.vocab_item_id == VocabItem.id)
        .where(VocabTaskItem.task_id == task.id)
        .order_by(VocabTaskItem.position)
    )
    return list(rows)


async def _fix_batch(
    session: AsyncSession,
    task: Task,
    event: Event,
    scenario_slug: str,
    today: date,
    now: datetime,
) -> None:
    """Choose and store the Task's batch: its Scenario's next available items for the
    Event's language and Level, in position order, up to its batch size.

    An item is available unless it's retired, already Introduced for this Event, or in
    the batch of another of the Event's Tasks that can still be completed (completed or
    not yet Missed), so two open Vocab Tasks never share items. A Missed Task's batch is
    never introduced, so its items go back into the pool.
    """
    assert task.vocab_batch_size is not None  # the check constraint, for Vocab Tasks
    introduced = select(ReviewState.vocab_item_id).where(ReviewState.event_id == event.id)
    held = (
        select(VocabTaskItem.vocab_item_id)
        .join(Task, VocabTaskItem.task_id == Task.id)
        .join(Milestone, Task.milestone_id == Milestone.id)
        .join(Plan, Milestone.plan_id == Plan.id)
        .where(
            Plan.event_id == event.id,
            or_(Task.completed_at.is_not(None), Task.date >= today),
        )
    )
    items = list(
        await session.scalars(
            select(VocabItem)
            .where(
                VocabItem.scenario_slug == scenario_slug,
                VocabItem.language == event.target_language,
                or_(VocabItem.level.is_(None), VocabItem.level == event.level),
                VocabItem.retired_at.is_(None),
                VocabItem.id.not_in(introduced),
                VocabItem.id.not_in(held),
            )
            .order_by(VocabItem.position, VocabItem.id)
            .limit(task.vocab_batch_size)
        )
    )
    session.add_all(
        VocabTaskItem(task_id=task.id, position=position, vocab_item_id=item.id)
        for position, item in enumerate(items, start=1)
    )
    task.vocab_batch_fixed_at = now
