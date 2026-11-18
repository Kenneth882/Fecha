from datetime import date
from uuid import UUID

import pytest

from app.services.srs import (
    AGAIN,
    EASY,
    GOOD,
    HARD,
    ReviewState,
    apply_grade,
    assigned_final_window_day,
    introduce,
)

ITEM = UUID("00000000-0000-0000-0000-000000000001")  # assigned Final Window day 1
DAY_2_ITEM = UUID("00000000-0000-0000-0000-000000000002")  # assigned Final Window day 2

# A 12-day Plan from 11 Nov: the Final Window is 21-22 Nov and the Event Day 23 Nov.
DEMO_EVENT_DAY = date(2026, 11, 23)
DAY_1, DAY_2 = date(2026, 11, 21), date(2026, 11, 22)


def test_an_introduced_item_is_first_due_the_day_after_with_fresh_sm2_state() -> None:
    state = introduce(ITEM, introduced_on=date(2026, 11, 18), event_day=DEMO_EVENT_DAY)

    assert state == ReviewState(
        ease=2.5,
        interval_days=0,
        repetitions=0,
        lapses=0,
        due_on=date(2026, 11, 19),
        reviewed_in_final_window=False,
        introduced_on=date(2026, 11, 18),
    )


def test_far_from_the_event_day_grades_follow_plain_sm2() -> None:
    far = date(2027, 6, 1)
    state = introduce(ITEM, introduced_on=date(2026, 1, 1), event_day=far)
    steps = [
        # (reviewed on, grade) -> (ease, interval, repetitions, lapses, due on)
        ((date(2026, 1, 2), GOOD), (2.5, 1, 1, 0, date(2026, 1, 3))),
        ((date(2026, 1, 3), EASY), (2.6, 6, 2, 0, date(2026, 1, 9))),
        ((date(2026, 1, 9), GOOD), (2.6, 16, 3, 0, date(2026, 1, 25))),  # 6 x 2.6 = 15.6
        ((date(2026, 1, 25), HARD), (2.46, 39, 4, 0, date(2026, 3, 5))),  # 16 x 2.46 = 39.36
        ((date(2026, 3, 5), AGAIN), (1.92, 1, 0, 1, date(2026, 3, 6))),
        ((date(2026, 3, 6), GOOD), (1.92, 1, 1, 1, date(2026, 3, 7))),
    ]

    for (reviewed_on, grade), (ease, interval, repetitions, lapses, due_on) in steps:
        state = apply_grade(state, ITEM, grade=grade, reviewed_on=reviewed_on, event_day=far)
        assert (
            state.ease,
            state.interval_days,
            state.repetitions,
            state.lapses,
            state.due_on,
        ) == (ease, interval, repetitions, lapses, due_on)
        assert not state.reviewed_in_final_window


def test_a_12_day_demo_item_graded_good_is_compressed_then_reviewed_on_final_window_day_1() -> None:
    event_day = DEMO_EVENT_DAY
    state = introduce(ITEM, introduced_on=date(2026, 11, 11), event_day=event_day)
    steps = [
        # reviewed on -> (interval, due on); the comment is SM-2's own interval and the cap
        (date(2026, 11, 12), (1, date(2026, 11, 13))),  # SM-2 1, cap 9 // 2 = 4
        (date(2026, 11, 13), (4, date(2026, 11, 17))),  # SM-2 6, cap 8 // 2 = 4
        (date(2026, 11, 17), (2, date(2026, 11, 19))),  # SM-2 10, cap 4 // 2 = 2
        (date(2026, 11, 19), (1, date(2026, 11, 20))),  # SM-2 5, cap 2 // 2 = 1
        (date(2026, 11, 20), (1, date(2026, 11, 21))),  # SM-2 3, cap 1; ITEM's day is 1
    ]

    for reviewed_on, expected in steps:
        state = apply_grade(state, ITEM, grade=GOOD, reviewed_on=reviewed_on, event_day=event_day)
        assert (state.interval_days, state.due_on) == expected
        assert not state.reviewed_in_final_window

    state = apply_grade(state, ITEM, grade=GOOD, reviewed_on=DAY_1, event_day=event_day)

    assert state.reviewed_in_final_window
    assert state.due_on is None


def test_the_final_window_day_is_chosen_from_the_item_id_the_same_way_every_time() -> None:
    assert assigned_final_window_day(ITEM, DEMO_EVENT_DAY) == DAY_1
    assert assigned_final_window_day(DAY_2_ITEM, DEMO_EVENT_DAY) == DAY_2


def test_a_day_2_item_graded_good_the_day_before_the_final_window_comes_due_on_day_2() -> None:
    state = introduce(DAY_2_ITEM, introduced_on=date(2026, 11, 18), event_day=DEMO_EVENT_DAY)
    state = apply_grade(
        state, DAY_2_ITEM, grade=GOOD, reviewed_on=date(2026, 11, 19), event_day=DEMO_EVENT_DAY
    )
    state = apply_grade(
        state, DAY_2_ITEM, grade=GOOD, reviewed_on=date(2026, 11, 20), event_day=DEMO_EVENT_DAY
    )

    # Compressed to 1 day, but SM-2 itself would wait 6, so day 2 is not later than that.
    assert (state.interval_days, state.due_on) == (1, DAY_2)


def test_items_introduced_the_day_before_the_final_window_are_first_due_on_day_1() -> None:
    for item in (ITEM, DAY_2_ITEM):
        state = introduce(item, introduced_on=date(2026, 11, 20), event_day=DEMO_EVENT_DAY)
        assert state.due_on == DAY_1


def test_again_the_day_before_the_final_window_brings_a_day_2_item_back_on_day_1() -> None:
    state = introduce(DAY_2_ITEM, introduced_on=date(2026, 11, 18), event_day=DEMO_EVENT_DAY)
    state = apply_grade(
        state, DAY_2_ITEM, grade=AGAIN, reviewed_on=date(2026, 11, 20), event_day=DEMO_EVENT_DAY
    )

    assert state.due_on == DAY_1


def reviewed_on_day_1(grade: int) -> ReviewState:
    state = introduce(ITEM, introduced_on=date(2026, 11, 20), event_day=DEMO_EVENT_DAY)
    return apply_grade(state, ITEM, grade=grade, reviewed_on=DAY_1, event_day=DEMO_EVENT_DAY)


def test_again_on_final_window_day_1_brings_the_item_back_on_day_2() -> None:
    state = reviewed_on_day_1(AGAIN)

    assert state.reviewed_in_final_window
    assert state.due_on == DAY_2


def test_after_a_final_window_review_nothing_more_is_due_unless_day_1_was_again() -> None:
    assert reviewed_on_day_1(HARD).due_on is None
    again_then_again = apply_grade(
        reviewed_on_day_1(AGAIN), ITEM, grade=AGAIN, reviewed_on=DAY_2, event_day=DEMO_EVENT_DAY
    )
    assert again_then_again.due_on is None
    assert again_then_again.reviewed_in_final_window


def test_ease_bottoms_out_at_1_3_after_repeated_agains() -> None:
    far = date(2027, 6, 1)
    state = introduce(ITEM, introduced_on=date(2026, 1, 1), event_day=far)
    eases = []
    for n in range(2, 6):
        state = apply_grade(state, ITEM, grade=AGAIN, reviewed_on=date(2026, 1, n), event_day=far)
        eases.append(state.ease)

    assert eases == [1.96, 1.42, 1.3, 1.3]


def test_nothing_is_introduced_in_the_final_window() -> None:
    with pytest.raises(ValueError):
        introduce(ITEM, introduced_on=DAY_1, event_day=DEMO_EVENT_DAY)


@pytest.mark.parametrize(
    ("grade", "reviewed_on"),
    [
        (6, date(2026, 11, 19)),
        (-1, date(2026, 11, 19)),
        (GOOD, date(2026, 11, 18)),  # the introduction day itself
        (GOOD, DEMO_EVENT_DAY),
    ],
)
def test_an_out_of_range_grade_or_review_day_is_refused(grade: int, reviewed_on: date) -> None:
    state = introduce(ITEM, introduced_on=date(2026, 11, 18), event_day=DEMO_EVENT_DAY)

    with pytest.raises(ValueError):
        apply_grade(state, ITEM, grade=grade, reviewed_on=reviewed_on, event_day=DEMO_EVENT_DAY)
