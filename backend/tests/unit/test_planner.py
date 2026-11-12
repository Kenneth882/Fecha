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


def revisit_on(p: DraftPlan, d: date) -> tuple[str, TaskKind]:
    """The 4th Task of a 30 or 45 min Plan Day."""
    return kinds_on(p, d)[3]


V, L, S = TaskKind.VOCAB, TaskKind.LISTEN, TaskKind.SPEAK


def test_harder_milestones_get_longer_blocks_ending_on_their_target_date() -> None:
    p = plan(12)

    # 10 ordinary days split by difficulty (1, 2, 2, 3) into blocks of 1, 2, 3 and 4 days.
    # Days 11 and 12 are the Final Window, outside every block.
    assert [m.target_date for m in p.milestones] == [day(1), day(3), day(6), day(10)]


def test_the_final_window_speaks_on_the_hardest_scenarios_then_listens_to_the_rest() -> None:
    p = plan(12)
    intro, experience, why, challenge = (m.scenario_slug for m in p.milestones)

    assert kinds_on(p, day(11)) == [(challenge, S), (why, S), (experience, L)]
    assert kinds_on(p, day(12)) == [(challenge, S), (why, S), (intro, L)]


def test_a_block_opens_with_vocab_and_listening_before_any_speaking() -> None:
    p = plan(12)
    experience = "interview.walking_through_your_experience"

    assert kinds_on(p, day(2)) == [(experience, V), (experience, V), (experience, L)]
    assert kinds_on(p, day(3)) == [(experience, V), (experience, L), (experience, S)]


def test_a_3_day_plan_has_2_scenarios_and_a_day_for_each() -> None:
    p = plan(3)
    first, second = (m.scenario_slug for m in p.milestones)

    assert kinds_on(p, day(1)) == [(first, V), (first, V), (first, L)]
    # Days 2 and 3 are the Final Window. The harder second Scenario has no earlier day,
    # so its Speak Tasks on day 2 become Listen Tasks.
    assert kinds_on(p, day(2)) == [(second, L), (second, L), (first, L)]
    assert kinds_on(p, day(3)) == [(second, S), (second, S), (second, L)]


@pytest.mark.parametrize(
    ("daily_budget", "minutes", "review_minutes"),
    [(15, [4, 4, 3], 4), (30, [6, 6, 5, 5], 8), (45, [9, 8, 8, 8], 12)],
)
def test_tasks_and_the_review_allowance_share_the_daily_budget(
    daily_budget: DailyBudget, minutes: list[int], review_minutes: int
) -> None:
    p = plan(12, daily_budget=daily_budget)
    first_day = sorted(
        (t for t in p.milestones[0].tasks if t.date == day(1)), key=lambda t: t.position
    )

    assert [t.estimated_minutes for t in first_day] == minutes
    assert review_allowance(daily_budget) == review_minutes


@pytest.mark.parametrize("days", [2, 1, 0, -1])
def test_an_event_day_fewer_than_3_days_away_is_refused(days: int) -> None:
    with pytest.raises(ValueError, match="3 days"):
        plan(days)


def test_a1_leans_on_listening_and_c1_on_speaking_for_the_same_event() -> None:
    a1, c1 = plan(12, level=Level.A1, daily_budget=30), plan(12, level=Level.C1, daily_budget=30)
    intro, experience = (m.scenario_slug for m in a1.milestones[:2])

    # Day 1 has no earlier Milestone, so the 4th Task stays on intro, and since it's
    # intro's first day it's a Listen Task at every Level.
    assert kinds_on(a1, day(1)) == [(intro, V), (intro, V), (intro, L), (intro, L)]
    assert kinds_on(c1, day(1)) == [(intro, V), (intro, L), (intro, L), (intro, L)]
    # A C1 User gets less vocab on a block's first day, and revisits by speaking.
    assert kinds_on(a1, day(2)) == [(experience, V), (experience, V), (experience, L), (intro, L)]
    assert kinds_on(c1, day(2)) == [(experience, V), (experience, L), (experience, L), (intro, S)]
    assert kinds_on(a1, day(3))[:3] == kinds_on(c1, day(3))[:3]
    assert revisit_on(a1, day(3))[1] is L
    assert revisit_on(c1, day(3))[1] is S


def test_b1_alternates_its_revisits_between_listening_and_speaking() -> None:
    p = plan(12, level=Level.B1, daily_budget=30)

    # Listen on odd Plan Days, Speak on even ones, from Plan Day 1.
    revisit_kinds = [revisit_on(p, day(n))[1] for n in range(1, 7)]
    assert revisit_kinds == [L, S, L, S, L, S]
