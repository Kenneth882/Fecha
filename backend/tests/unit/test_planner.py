from datetime import date, timedelta

import pytest

from app.services.catalog import EventType
from app.services.planner import (
    DailyBudget,
    DraftPlan,
    Level,
    TaskKind,
    build_plan,
    review_allowance,
)

START = date(2026, 11, 11)


def plan(
    days: int,
    event_type: EventType = EventType.INTERVIEW,
    level: Level = Level.B1,
    daily_budget: DailyBudget = 15,
) -> DraftPlan:
    return build_plan(
        event_type=event_type,
        level=level,
        daily_budget=daily_budget,
        start_date=START,
        event_day=START + timedelta(days=days),
    )


def test_a_12_day_interview_plan_covers_the_4_most_essential_scenarios_easy_to_hard() -> None:
    milestones = plan(12).milestones

    assert [m.scenario_slug for m in milestones] == [
        "interview.introducing_yourself",
        "interview.walking_through_your_experience",
        "interview.why_this_role",
        "interview.describing_a_challenge",
    ]
    assert [m.position for m in milestones] == [1, 2, 3, 4]


def day(n: int) -> date:
    """Plan Day n, counting the start date as Plan Day 1."""
    return START + timedelta(days=n - 1)


def kinds_on(p: DraftPlan, d: date) -> list[tuple[str, TaskKind]]:
    tasks = [(m.scenario_slug, t) for m in p.milestones for t in m.tasks if t.date == d]
    return [(slug, t.kind) for slug, t in sorted(tasks, key=lambda pair: pair[1].position)]


V, L, S = TaskKind.VOCAB, TaskKind.LISTEN, TaskKind.SPEAK


def test_harder_milestones_get_longer_blocks_ending_on_their_target_date() -> None:
    p = plan(12)

    # 10 ordinary days split by difficulty (1, 2, 2, 3) into blocks of 1, 2, 3 and 4 days.
    # Until the Final Window rules land (#20), its 2 days extend the last block.
    assert [len(m.tasks) for m in p.milestones] == [3, 6, 9, 18]
    assert [m.target_date for m in p.milestones] == [day(1), day(3), day(6), day(12)]


def test_a_block_opens_with_vocab_and_listening_before_any_speaking() -> None:
    p = plan(12)
    experience = "interview.walking_through_your_experience"

    assert kinds_on(p, day(2)) == [(experience, V), (experience, V), (experience, L)]
    assert kinds_on(p, day(3)) == [(experience, V), (experience, L), (experience, S)]


def test_a_3_day_plan_has_2_scenarios_and_a_day_for_each() -> None:
    p = plan(3)
    first, second = (m.scenario_slug for m in p.milestones)

    assert kinds_on(p, day(1)) == [(first, V), (first, V), (first, L)]
    assert kinds_on(p, day(2)) == [(second, V), (second, V), (second, L)]
    assert kinds_on(p, day(3)) == [(second, V), (second, L), (second, S)]


@pytest.mark.parametrize(
    ("daily_budget", "minutes", "review_minutes"),
    [(15, [4, 4, 3], 4), (30, [8, 7, 7], 8), (45, [11, 11, 11], 12)],
)
def test_tasks_and_the_review_allowance_share_the_daily_budget(
    daily_budget: DailyBudget, minutes: list[int], review_minutes: int
) -> None:
    p = plan(12, daily_budget=daily_budget)
    first_day = sorted(p.milestones[0].tasks, key=lambda t: t.position)

    assert [t.estimated_minutes for t in first_day] == minutes
    assert review_allowance(daily_budget) == review_minutes


@pytest.mark.parametrize("days", [2, 1, 0, -1])
def test_an_event_day_fewer_than_3_days_away_is_refused(days: int) -> None:
    with pytest.raises(ValueError, match="3 days"):
        plan(days)
