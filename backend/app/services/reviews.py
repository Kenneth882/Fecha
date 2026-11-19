"""The Review Queue of a User's Event, and grading its Reviews with `srs.py`.

Reviews are never Missed: an overdue item stays in the queue until it's graded. Each
Grade appends one row to the `reviews` log, which is never updated or deleted.
"""

import uuid
from datetime import date, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.review import Review, ReviewState
from app.models.user import User
from app.models.vocab import VocabItem
from app.schemas.event import EventState
from app.schemas.review import DueReview, Grade, ReviewGrade, ReviewQueue, ReviewResult
from app.services import srs
from app.services.catalog import stored_scenario
from app.services.events import EventAlreadyPastError, event_state, own_event
from app.services.local_time import local_today

# The 0-5 Grade behind each of the User's buttons.
_GRADE_VALUES: dict[Grade, int] = {
    Grade.AGAIN: srs.AGAIN,
    Grade.HARD: srs.HARD,
    Grade.GOOD: srs.GOOD,
    Grade.EASY: srs.EASY,
}


class VocabItemNotIntroducedError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "vocab_item_not_introduced"
    message = "That Vocab Item hasn't been introduced for this Event"


class EventDayReachedError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "event_day_reached"
    message = "It's the Event Day: there are no more Reviews"


class ReviewNotDueError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "review_not_due"
    message = "That Vocab Item isn't due for Review today"


async def review_queue(
    session: AsyncSession, user: User, event_id: uuid.UUID, now: datetime
) -> ReviewQueue:
    """The Event's Vocab Items due on the User's local today or earlier, oldest first.

    Empty on the Event Day and for a Past Event. Raises EventNotFoundError if there's no
    such Event or it's another User's.
    """
    event = await own_event(session, user, event_id)
    today = local_today(now, user.timezone)
    if event_state(event, today) is not EventState.ACTIVE:
        return ReviewQueue(count=0, items=[])
    rows = await session.execute(
        select(ReviewState.due_on, VocabItem)
        .join(VocabItem, ReviewState.vocab_item_id == VocabItem.id)
        .where(ReviewState.event_id == event.id, ReviewState.due_on <= today)
        .order_by(
            ReviewState.due_on,
            ReviewState.introduced_on,
            VocabItem.scenario_slug,
            VocabItem.position,
            VocabItem.id,
        )
    )
    items = [_due_review(item, due_on) for due_on, item in rows]
    return ReviewQueue(count=len(items), items=items)


def _due_review(item: VocabItem, due_on: date | None) -> DueReview:
    assert due_on is not None  # the queue's query keeps only due_on <= today
    return DueReview(
        vocab_item_id=item.id,
        phrase=item.phrase,
        translation=item.translation,
        scenario_title=stored_scenario(item.scenario_slug).title,
        due_on=due_on,
    )


async def grade_review(
    session: AsyncSession, user: User, event_id: uuid.UUID, data: ReviewGrade, now: datetime
) -> ReviewResult:
    """Grade one of the Event's due Reviews at `now`: apply `srs.apply_grade` to its
    Review State and append a Review to the log.

    The Review State's row stays locked from the read until the commit, so two Grades
    for the same item can't both pass the due check. The Event's row is share-locked
    too, so it can't be abandoned between the state check and the commit.

    Raises EventNotFoundError as `review_queue` does, EventAlreadyPastError for a Past
    Event, EventDayReachedError on the Event Day, VocabItemNotIntroducedError for an
    item that isn't Introduced for this Event, and ReviewNotDueError unless it's in
    today's Review Queue, so a second Grade the same day is refused.
    """
    event = await own_event(session, user, event_id, for_share=True)
    today = local_today(now, user.timezone)
    match event_state(event, today):
        case EventState.PAST:
            raise EventAlreadyPastError
        case EventState.EVENT_DAY:
            raise EventDayReachedError
    state = await session.scalar(
        select(ReviewState)
        .where(ReviewState.event_id == event.id, ReviewState.vocab_item_id == data.vocab_item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if state is None:
        raise VocabItemNotIntroducedError
    if state.due_on is None or state.due_on > today:
        raise ReviewNotDueError
    grade_value = _GRADE_VALUES[data.grade]
    new_state = srs.apply_grade(
        _srs_state(state),
        state.vocab_item_id,
        grade=grade_value,
        reviewed_on=today,
        event_day=event.event_day,
    )
    for field, value in new_state.model_dump().items():
        setattr(state, field, value)
    session.add(
        Review(
            event_id=event.id,
            vocab_item_id=state.vocab_item_id,
            plan_day=today,
            grade=grade_value,
            reviewed_at=now,
        )
    )
    await session.commit()
    return ReviewResult(vocab_item_id=state.vocab_item_id, due_on=new_state.due_on)


def _srs_state(row: ReviewState) -> srs.ReviewState:
    return srs.ReviewState(
        ease=row.ease,
        interval_days=row.interval_days,
        repetitions=row.repetitions,
        lapses=row.lapses,
        due_on=row.due_on,
        reviewed_in_final_window=row.reviewed_in_final_window,
        introduced_on=row.introduced_on,
    )
