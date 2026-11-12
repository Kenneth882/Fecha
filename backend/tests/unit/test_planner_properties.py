"""Invariants the planner keeps for every Event Type, Level, Daily Budget and date pair."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from app.services.catalog import EventType, find_scenario
from app.services.planner import (
    FINAL_WINDOW_DAYS,
    DailyBudget,
    DraftPlan,
    DraftTask,
    Level,
    TaskKind,
    build_plan,
    review_allowance,
)


@dataclass(frozen=True)
class Inputs:
    event_type: EventType
    level: Level
    daily_budget: DailyBudget
    start_date: date
    event_day: date

    def plan(self) -> DraftPlan:
        return build_plan(
            event_type=self.event_type,
            level=self.level,
            daily_budget=self.daily_budget,
            start_date=self.start_date,
            event_day=self.event_day,
        )


@st.composite
def inputs(draw: st.DrawFn) -> Inputs:
    start = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)))
    return Inputs(
        event_type=draw(st.sampled_from(EventType)),
        level=draw(st.sampled_from(Level)),
        daily_budget=draw(st.sampled_from((15, 30, 45))),
        start_date=start,
        event_day=start + timedelta(days=draw(st.integers(min_value=3, max_value=60))),
    )


def all_tasks(p: DraftPlan) -> list[DraftTask]:
    return [t for m in p.milestones for t in m.tasks]


def difficulty(slug: str) -> int:
    scenario = find_scenario(slug)
    assert scenario is not None, slug
    return scenario.difficulty


@given(inputs())
def test_no_task_falls_before_the_start_or_on_or_after_the_event_day(i: Inputs) -> None:
    for task in all_tasks(i.plan()):
        assert i.start_date <= task.date < i.event_day


@given(inputs())
def test_every_plan_day_has_3_tasks_at_15_minutes_and_4_at_30_or_45(i: Inputs) -> None:
    by_day: dict[date, list[int]] = {}
    for task in all_tasks(i.plan()):
        by_day.setdefault(task.date, []).append(task.position)

    plan_days = (i.event_day - i.start_date).days
    task_count = 3 if i.daily_budget == 15 else 4
    assert sorted(by_day) == [i.start_date + timedelta(days=n) for n in range(plan_days)]
    assert all(sorted(positions) == list(range(1, task_count + 1)) for positions in by_day.values())


@given(inputs())
def test_each_days_tasks_and_review_allowance_fit_inside_the_daily_budget(i: Inputs) -> None:
    minutes: Counter[date] = Counter()
    for task in all_tasks(i.plan()):
        assert task.estimated_minutes >= 1
        minutes[task.date] += task.estimated_minutes

    for total in minutes.values():
        assert total + review_allowance(i.daily_budget) <= i.daily_budget


@given(inputs())
def test_the_scenario_count_follows_the_k_formula(i: Inputs) -> None:
    ordinary_days = (i.event_day - i.start_date).days - FINAL_WINDOW_DAYS

    # The spec's K = clamp(round(D / 2.5), 2, catalog size), with 6 Scenarios per type.
    assert len(i.plan().milestones) == min(max(round(ordinary_days / 2.5), 2), 6)


@given(inputs())
def test_milestones_are_distinct_numbered_and_ordered_easy_to_hard(i: Inputs) -> None:
    milestones = i.plan().milestones
    slugs = [m.scenario_slug for m in milestones]
    difficulties = [difficulty(slug) for slug in slugs]

    assert len(set(slugs)) == len(slugs)
    assert all(slug.startswith(f"{i.event_type}.") for slug in slugs)
    assert [m.position for m in milestones] == list(range(1, len(milestones) + 1))
    assert difficulties == sorted(difficulties)


@given(inputs())
def test_a_harder_scenario_never_gets_fewer_tasks_than_an_easier_one(i: Inputs) -> None:
    counts = [(difficulty(m.scenario_slug), len(m.tasks)) for m in i.plan().milestones]

    for easy_difficulty, easy_count in counts:
        for hard_difficulty, hard_count in counts:
            if hard_difficulty > easy_difficulty:
                assert hard_count >= easy_count


@given(inputs())
def test_each_target_date_ends_its_milestones_block_before_the_final_window(i: Inputs) -> None:
    milestones = i.plan().milestones
    first_final_window_day = i.event_day - timedelta(days=FINAL_WINDOW_DAYS)
    targets = [m.target_date for m in milestones]

    assert targets == sorted(set(targets))
    # Only a 3-day Plan's last block is empty; it ends on the first Final Window day.
    assert all(t < first_final_window_day for t in targets[:-1])
    assert targets[-1] <= first_final_window_day
    for m in milestones:
        assert any(t.date == m.target_date and t.position == 1 for t in m.tasks)


@given(inputs())
def test_no_speak_task_comes_on_a_milestones_first_day(i: Inputs) -> None:
    for m in i.plan().milestones:
        first_day = min(t.date for t in m.tasks)
        assert all(t.kind is not TaskKind.SPEAK for t in m.tasks if t.date == first_day)


@given(inputs())
def test_the_same_input_gives_an_equal_plan(i: Inputs) -> None:
    assert i.plan() == i.plan()


def final_window(i: Inputs) -> set[date]:
    return {i.event_day - timedelta(days=n) for n in range(1, FINAL_WINDOW_DAYS + 1)}


@given(inputs())
def test_the_final_window_has_no_vocab_task(i: Inputs) -> None:
    for task in all_tasks(i.plan()):
        if task.date in final_window(i):
            assert task.kind is not TaskKind.VOCAB


@given(inputs())
def test_every_chosen_scenario_appears_in_the_final_window_when_slots_allow(i: Inputs) -> None:
    p = i.plan()
    slots = sum(1 for t in all_tasks(p) if t.date in final_window(i))

    if len(p.milestones) <= slots:
        for m in p.milestones:
            assert any(t.date in final_window(i) for t in m.tasks), m.scenario_slug


@given(inputs())
def test_the_4th_task_never_belongs_to_a_later_milestone_than_the_days_own(i: Inputs) -> None:
    owner = {(t.date, t.position): m.position for m in i.plan().milestones for t in m.tasks}

    for (d, position), milestone in owner.items():
        if position == 4 and d not in final_window(i):
            assert milestone <= owner[(d, 1)]
