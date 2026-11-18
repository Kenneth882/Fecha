"""Invariants of deadline-compressed SM-2 for any Plan dates, Grades and item ids."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from app.services.srs import (
    AGAIN,
    GOOD,
    MIN_EASE,
    ReviewState,
    apply_grade,
    assigned_final_window_day,
    first_final_window_day,
    interval_cap,
    introduce,
)

grades = st.integers(min_value=0, max_value=5)


@dataclass(frozen=True)
class Item:
    """An item introduced on some ordinary Plan Day of a valid Plan (3-60 days long)."""

    id: UUID
    introduced_on: date
    event_day: date


@st.composite
def items(draw: st.DrawFn) -> Item:
    event_day = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)))
    start = event_day - timedelta(days=draw(st.integers(min_value=3, max_value=60)))
    last_ordinary_day = first_final_window_day(event_day) - timedelta(days=1)
    introduced_on = draw(st.dates(min_value=start, max_value=last_ordinary_day))
    return Item(id=draw(st.uuids()), introduced_on=introduced_on, event_day=event_day)


@dataclass(frozen=True)
class Graded:
    reviewed_on: date
    grade: int
    after: ReviewState


def clear_the_queue_daily(item: Item, data: st.DataObject) -> tuple[ReviewState, list[Graded]]:
    """A User who reviews the item every day it's due, with any Grade each time."""
    state = introduce(item.id, introduced_on=item.introduced_on, event_day=item.event_day)
    history: list[Graded] = []
    today = item.introduced_on + timedelta(days=1)
    while today < item.event_day:
        if state.due_on is not None and state.due_on <= today:
            grade = data.draw(grades)
            state = apply_grade(
                state, item.id, grade=grade, reviewed_on=today, event_day=item.event_day
            )
            history.append(Graded(today, grade, state))
        today += timedelta(days=1)
    return state, history


@given(items(), st.data())
def test_a_user_who_clears_the_queue_daily_reviews_every_item_in_the_final_window(
    item: Item, data: st.DataObject
) -> None:
    state, history = clear_the_queue_daily(item, data)

    first_day = first_final_window_day(item.event_day)
    assert any(g.reviewed_on >= first_day for g in history)
    assert state.reviewed_in_final_window
    assert state.due_on is None


@given(items())
def test_an_item_always_graded_good_is_first_reviewed_on_its_own_final_window_day(
    item: Item,
) -> None:
    # Items introduced in the last 2 ordinary days are still on SM-2's 1-day first
    # interval, so they come back on day 1; earlier ones spread by id across both days.
    first_day = first_final_window_day(item.event_day)
    if item.introduced_on > first_day - timedelta(days=3):
        return
    state = introduce(item.id, introduced_on=item.introduced_on, event_day=item.event_day)
    today = item.introduced_on + timedelta(days=1)
    while today < first_day:
        if state.due_on == today:
            state = apply_grade(
                state, item.id, grade=GOOD, reviewed_on=today, event_day=item.event_day
            )
        today += timedelta(days=1)

    assert state.due_on == assigned_final_window_day(item.id, item.event_day)


@given(items(), st.data())
def test_nothing_is_due_before_the_day_after_introduction_or_on_or_after_the_event_day(
    item: Item, data: st.DataObject
) -> None:
    first = introduce(item.id, introduced_on=item.introduced_on, event_day=item.event_day)
    _, history = clear_the_queue_daily(item, data)

    for due_on in [first.due_on, *(g.after.due_on for g in history)]:
        if due_on is not None:
            assert item.introduced_on < due_on < item.event_day
    for g in history:
        assert g.after.due_on is None or g.after.due_on > g.reviewed_on


@given(items(), st.data())
def test_ease_never_goes_below_the_floor_and_intervals_never_exceed_the_cap(
    item: Item, data: st.DataObject
) -> None:
    _, history = clear_the_queue_daily(item, data)

    for g in history:
        assert g.after.ease >= MIN_EASE
        assert 1 <= g.after.interval_days <= interval_cap(g.reviewed_on, item.event_day)


@given(items(), st.data())
def test_again_brings_an_item_back_the_next_day_except_on_final_window_day_2(
    item: Item, data: st.DataObject
) -> None:
    _, history = clear_the_queue_daily(item, data)

    final_window_day_2 = first_final_window_day(item.event_day) + timedelta(days=1)
    for g in history:
        if g.grade == AGAIN:
            expected = None if g.reviewed_on == final_window_day_2 else g.reviewed_on + timedelta(1)
            assert g.after.due_on == expected


@given(
    st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)),
    st.integers(min_value=0, max_value=60),
    st.integers(min_value=1, max_value=60),
)
def test_the_interval_cap_never_increases_as_the_event_day_nears(
    today: date, days_ahead: int, later_by: int
) -> None:
    event_day = today + timedelta(days=days_ahead)

    assert interval_cap(today + timedelta(days=later_by), event_day) <= interval_cap(
        today, event_day
    )
    assert interval_cap(today, event_day) >= 1


@given(items(), st.lists(grades, min_size=1, max_size=10))
def test_the_same_input_gives_an_equal_review_state(item: Item, grade_sequence: list[int]) -> None:
    def run() -> ReviewState:
        state = introduce(item.id, introduced_on=item.introduced_on, event_day=item.event_day)
        for n, grade in enumerate(grade_sequence, start=1):
            reviewed_on = item.introduced_on + timedelta(days=n)
            if reviewed_on >= item.event_day:
                break
            state = apply_grade(
                state, item.id, grade=grade, reviewed_on=reviewed_on, event_day=item.event_day
            )
        return state

    assert run() == run()
