"""Deadline-compressed SM-2: when each Introduced Vocab Item's next Review is due.

Pure and deterministic: no clock, no randomness, no I/O. The caller passes the Plan Day
a Grade was given on and the Event Day, and gets back the new Review State.

Three rules sit on top of plain SM-2 (see "Scheduling algorithm" in the README):

1. Compression: an interval is at most half the days left before the Final Window, and
   at least 1, so the cap never increases as the Event Day nears.
2. Final Window clamp: an item not yet reviewed in the Final Window whose compressed due
   date reaches day 1 is assigned day 1 or day 2, chosen from its id, but never later
   than its "natural" due date: this step's SM-2 interval before the cap is applied.
3. In the Final Window a Grade marks the item reviewed there; after that only Again on
   day 1 brings it back (on day 2). Nothing is ever due on or after the Event Day.
"""

import hashlib
from datetime import date, timedelta
from math import floor
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.services.planner import FINAL_WINDOW_DAYS

INITIAL_EASE = 2.5
MIN_EASE = 1.3

# The Grades behind the User's four buttons. Of these only Again is below PASSING_GRADE,
# so only Again counts as forgotten; srs.py treats any Grade below it the same way.
AGAIN, HARD, GOOD, EASY = 1, 3, 4, 5
PASSING_GRADE = 3
MIN_GRADE, MAX_GRADE = 0, 5

# SM-2's fixed first two intervals, by repetition count.
_FIRST_INTERVALS = {1: 1, 2: 6}


class ReviewState(BaseModel):
    """The spaced-repetition progress of one Introduced Vocab Item within one Event.

    `interval_days` is the last interval used, after compression, and the next SM-2
    interval grows from it. Near the Final Window the clamp can move `due_on` a day off
    the last Review plus `interval_days`. `due_on` is None once nothing more is
    scheduled before the Event Day.
    """

    model_config = ConfigDict(frozen=True)

    ease: float
    interval_days: int
    repetitions: int
    lapses: int
    due_on: date | None
    reviewed_in_final_window: bool
    introduced_on: date


def first_final_window_day(event_day: date) -> date:
    """Final Window day 1, the first of the two Plan Days just before the Event Day."""
    return event_day - timedelta(days=FINAL_WINDOW_DAYS)


def assigned_final_window_day(item_id: UUID, event_day: date) -> date:
    """The Final Window day (1 or 2) an item is assigned to: stable across processes."""
    offset = hashlib.sha256(item_id.bytes).digest()[0] % FINAL_WINDOW_DAYS
    return first_final_window_day(event_day) + timedelta(days=offset)


def interval_cap(today: date, event_day: date) -> int:
    """The longest interval allowed for a Review on `today`: half the days left before
    the Final Window, and never less than 1."""
    days_left = (first_final_window_day(event_day) - today).days
    return max(1, days_left // 2)


def introduce(item_id: UUID, *, introduced_on: date, event_day: date) -> ReviewState:
    """The Review State of an item introduced today: first due the next day.

    Raises ValueError if `introduced_on` is in the Final Window or later, where no Vocab
    Items are introduced.
    """
    if introduced_on >= first_final_window_day(event_day):
        raise ValueError("no Vocab Item is introduced in the Final Window or later")
    next_day = introduced_on + timedelta(days=1)
    return ReviewState(
        ease=INITIAL_EASE,
        interval_days=0,
        repetitions=0,
        lapses=0,
        due_on=_clamp(
            item_id, compressed_due_on=next_day, natural_due_on=next_day, event_day=event_day
        ),
        reviewed_in_final_window=False,
        introduced_on=introduced_on,
    )


def apply_grade(
    state: ReviewState, item_id: UUID, *, grade: int, reviewed_on: date, event_day: date
) -> ReviewState:
    """The Review State after the User grades the item on the Plan Day `reviewed_on`.

    Raises ValueError for a Grade outside 0-5, or a Review before the day after
    introduction or on or after the Event Day.
    """
    if not MIN_GRADE <= grade <= MAX_GRADE:
        raise ValueError(f"a Grade is 0-5, got {grade}")
    if not state.introduced_on < reviewed_on < event_day:
        raise ValueError("a Review falls after its introduction day and before the Event Day")

    ease = max(MIN_EASE, round(state.ease + _ease_change(grade), 2))
    if grade < PASSING_GRADE:
        repetitions, lapses, sm2_interval = 0, state.lapses + 1, 1
    else:
        repetitions, lapses = state.repetitions + 1, state.lapses
        sm2_interval = _FIRST_INTERVALS.get(repetitions) or _round_half_up(
            state.interval_days * ease
        )
    interval = min(sm2_interval, interval_cap(reviewed_on, event_day))

    in_final_window = reviewed_on >= first_final_window_day(event_day)
    if in_final_window:
        retry_on = reviewed_on + timedelta(days=1)
        due_on = retry_on if grade < PASSING_GRADE and retry_on < event_day else None
    else:
        due_on = _clamp(
            item_id,
            compressed_due_on=reviewed_on + timedelta(days=interval),
            natural_due_on=reviewed_on + timedelta(days=sm2_interval),
            event_day=event_day,
        )

    return state.model_copy(
        update={
            "ease": ease,
            "interval_days": interval,
            "repetitions": repetitions,
            "lapses": lapses,
            "due_on": due_on,
            "reviewed_in_final_window": state.reviewed_in_final_window or in_final_window,
        }
    )


def _clamp(
    item_id: UUID, *, compressed_due_on: date, natural_due_on: date, event_day: date
) -> date:
    """Move a compressed due date that reaches the Final Window onto the item's Final
    Window day, but never later than its natural due date (this step's SM-2 interval,
    before the cap).

    Compression alone never reaches past day 1, so the natural due date is what lets
    half the items wait for day 2. Again and a first Review have a natural due date of
    the next day, so they're never moved later.
    """
    if compressed_due_on < first_final_window_day(event_day):
        return compressed_due_on
    return min(assigned_final_window_day(item_id, event_day), natural_due_on)


def _ease_change(grade: int) -> float:
    """The standard SM-2 ease update: +0.1 for 5, 0 for 4, down to -0.8 for 0."""
    miss = MAX_GRADE - grade
    return 0.1 - miss * (0.08 + miss * 0.02)


def _round_half_up(x: float) -> int:
    """Round to the nearest whole day, halves up (Python's round() goes to even)."""
    return floor(x + 0.5)
