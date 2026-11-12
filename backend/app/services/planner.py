"""The backward planner: from an Event's settings to a draft Plan of Milestones and Tasks.

Pure and deterministic: no clock, no randomness, no I/O. The caller passes the start
date (the User's local today) and gets back plain data, which the Event service stores
as a Plan version.
"""

from datetime import date, timedelta
from enum import StrEnum
from fractions import Fraction
from math import floor
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict

from app.services.catalog import EventType, Scenario, scenarios_for

DailyBudget = Literal[15, 30, 45]


class Level(StrEnum):
    """The User's proficiency in the Event's target language (a trimmed CEFR scale)."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"


class TaskKind(StrEnum):
    """What a Task asks of the User: learn Vocab Items, listen to a dialogue, or speak."""

    VOCAB = "vocab"
    LISTEN = "listen"
    SPEAK = "speak"


class DraftTask(BaseModel):
    """A planned Task, not yet stored. `position` orders it within its Plan Day, from 1."""

    model_config = ConfigDict(frozen=True)

    date: date
    kind: TaskKind
    position: int
    estimated_minutes: int


class DraftMilestone(BaseModel):
    """A chosen Scenario with its place in the order (from 1), target date and Tasks."""

    model_config = ConfigDict(frozen=True)

    scenario_slug: str
    position: int
    target_date: date
    tasks: tuple[DraftTask, ...]


class DraftPlan(BaseModel):
    """A Plan before it is stored: its Milestones in order, easy to hard."""

    model_config = ConfigDict(frozen=True)

    milestones: tuple[DraftMilestone, ...]


FINAL_WINDOW_DAYS = 2
MIN_PLAN_DAYS = 3
# K, the number of Scenarios, is about one per this many ordinary days.
ORDINARY_DAYS_PER_SCENARIO = 2.5

# Minutes of each Daily Budget kept back for the Review Queue, which runs alongside the
# Tasks (Week 3). The Tasks share whatever is left.
_REVIEW_ALLOWANCE: dict[DailyBudget, int] = {15: 4, 30: 8, 45: 12}

_V, _L, _S = TaskKind.VOCAB, TaskKind.LISTEN, TaskKind.SPEAK
_LATER_DAY = (_V, _L, _S)
# A Final Window day. Its 4th position, like an ordinary day's, exists only at 30/45 min.
_FINAL_WINDOW_DAY = (_S, _S, _L, _L)
# The position of an ordinary day's revisit, the Task that goes back to an earlier Milestone.
_REVISIT_POSITION = 4


class _LevelStyle(NamedTuple):
    """How a Level shapes the Plan: a block's first day, and the revisit kinds in turn."""

    first_day: tuple[TaskKind, ...]
    revisits: tuple[TaskKind, ...]


# Beginners revisit by listening. Advanced Users already know more phrases, so one
# first-day Vocab Task becomes listening and they revisit by speaking. B1 alternates.
_BEGINNER = _LevelStyle(first_day=(_V, _V, _L), revisits=(_L,))
_LEVEL_STYLE: dict[Level, _LevelStyle] = {
    Level.A1: _BEGINNER,
    Level.A2: _BEGINNER,
    Level.B1: _LevelStyle(first_day=(_V, _V, _L), revisits=(_L, _S)),
    Level.B2: _LevelStyle(first_day=(_V, _L, _L), revisits=(_S,)),
    Level.C1: _LevelStyle(first_day=(_V, _L, _L), revisits=(_S,)),
}


class _Planned(NamedTuple):
    """A Task while the Plan is being built, before minutes are attached."""

    date: date
    kind: TaskKind
    position: int


def review_allowance(daily_budget: DailyBudget) -> int:
    """Minutes of the Daily Budget kept for Reviews; the Tasks never use them."""
    return _REVIEW_ALLOWANCE[daily_budget]


def tasks_per_day(daily_budget: DailyBudget) -> int:
    """How many Tasks every Plan Day has: 3 at 15 min, 4 at 30 and 45 min."""
    return 3 if daily_budget == 15 else 4


def build_plan(
    *,
    event_type: EventType,
    level: Level,
    daily_budget: DailyBudget,
    start_date: date,
    event_day: date,
) -> DraftPlan:
    """A draft Plan from Plan Day 1 (`start_date`) up to the day before `event_day`.

    The K most essential Scenarios of the Event Type become Milestones, ordered easy to
    hard. Each gets a block of consecutive ordinary days, longer for harder Scenarios,
    and its target date is the block's last day. A block opens with Vocab, Vocab, Listen
    (Vocab, Listen, Listen at B2/C1); its later days are Vocab, Listen, Speak.

    At 30 and 45 min, each ordinary day's 4th Task revisits an earlier Milestone (the
    current one on the first block), by listening at A1/A2, speaking at B2/C1 and
    alternating at B1. The Final Window's 2 days have no Vocab Tasks: Speak Tasks on
    the hardest Scenarios come first, then Listen Tasks for the ones not yet covered.
    No Milestone is spoken on its first day.

    Raises ValueError if `event_day` is fewer than 3 days after `start_date`, or the
    Daily Budget isn't one of 15, 30 or 45 minutes.
    """
    plan_days = (event_day - start_date).days
    if plan_days < MIN_PLAN_DAYS:
        raise ValueError(f"The Event Day must be at least {MIN_PLAN_DAYS} days after the start")
    if daily_budget not in _REVIEW_ALLOWANCE:
        raise ValueError(f"Unsupported Daily Budget: {daily_budget}")

    ordinary_days = plan_days - FINAL_WINDOW_DAYS
    chosen = _choose_scenarios(scenarios_for(event_type), ordinary_days)
    lengths = _block_lengths([s.difficulty for s in chosen], ordinary_days)
    task_count = tasks_per_day(daily_budget)
    minutes = _task_minutes(daily_budget, task_count)
    style = _LEVEL_STYLE[level]
    caps = _revisit_caps(chosen, lengths)

    # Each Milestone's Tasks, filled in Plan Day order.
    tasks: list[list[_Planned]] = [[] for _ in chosen]
    target_dates: list[date] = []
    day = start_date
    for current, length in enumerate(lengths):
        for block_day in range(length):
            pattern = style.first_day if block_day == 0 else _LATER_DAY
            tasks[current].extend(
                _Planned(day, kind, position) for position, kind in enumerate(pattern, start=1)
            )
            if task_count == _REVISIT_POSITION:
                revisited = _revisit_target(current, chosen, tasks, caps)
                plan_day = (day - start_date).days + 1
                kind = style.revisits[(plan_day - 1) % len(style.revisits)]
                tasks[revisited].append(
                    _Planned(
                        day,
                        _no_speaking_on_first_day(kind, tasks[revisited], day),
                        _REVISIT_POSITION,
                    )
                )
            day += timedelta(days=1)
        # An empty block (only the last, in a 3-day Plan) ends on the first Final Window day.
        target_dates.append(day - timedelta(days=1) if length else day)

    final_window = [day + timedelta(days=n) for n in range(FINAL_WINDOW_DAYS)]
    _plan_final_window(final_window, _FINAL_WINDOW_DAY[:task_count], chosen, tasks)

    return DraftPlan(
        milestones=tuple(
            DraftMilestone(
                scenario_slug=scenario.slug,
                position=position,
                target_date=target_date,
                tasks=tuple(
                    DraftTask(
                        date=t.date,
                        kind=t.kind,
                        position=t.position,
                        estimated_minutes=minutes[t.position - 1],
                    )
                    for t in sorted(milestone_tasks, key=lambda t: (t.date, t.position))
                ),
            )
            for position, (scenario, target_date, milestone_tasks) in enumerate(
                zip(chosen, target_dates, tasks, strict=True), start=1
            )
        )
    )


def _revisit_target(
    current: int, chosen: list[Scenario], tasks: list[list[_Planned]], caps: list[float]
) -> int:
    """The Milestone an ordinary day's revisit goes to.

    On the first block there's no earlier Milestone, so it's the current one. Otherwise
    it's the earlier Milestone with the fewest Tasks so far, hardest first, preferring
    those still under their cap.
    """
    if current == 0:
        return 0
    return min(
        range(current),
        key=lambda i: (len(tasks[i]) >= caps[i], len(tasks[i]), -chosen[i].difficulty, -i),
    )


def _revisit_caps(chosen: list[Scenario], lengths: list[int]) -> list[float]:
    """The Task count past which revisits prefer other Milestones.

    A Milestone's own block gives it 3 Tasks a day whatever happens later. Capping each
    Milestone at the smallest such count among harder Milestones keeps revisits from
    lifting an easier Scenario above a harder one. When every earlier Milestone is at
    its cap the revisit still goes to one of them, and the Final Window's top-ups
    restore the order.
    """
    own = [len(_LATER_DAY) * length for length in lengths]
    return [
        min(
            (own[j] for j, harder in enumerate(chosen) if harder.difficulty > s.difficulty),
            default=float("inf"),
        )
        for s in chosen
    ]


def _plan_final_window(
    days: list[date],
    pattern: tuple[TaskKind, ...],
    chosen: list[Scenario],
    tasks: list[list[_Planned]],
) -> None:
    """Fill the Final Window: Speak Tasks first, then Listen Tasks, never Vocab.

    - A Speak Task goes to the hardest Scenario not yet spoken that day. If the Listen
      Tasks left couldn't cover every Scenario the window hasn't touched yet, it goes to
      the hardest of those instead (only at 15 min with 5 or 6 Scenarios).
    - A Listen Task goes to a Scenario the window hasn't covered yet, hardest first, so
      every Scenario gets a Task when the Task count allows it. Once all are covered,
      Listen Tasks rotate: fewest Final Window Tasks first, hardest first.
    - Either kind first tops up a harder Scenario that has no more Tasks than an easier
      one, so harder Scenarios never end up with fewer Tasks.
    - A Speak Task on a Scenario with no earlier Task becomes a Listen Task.
    """
    covered: set[int] = set()
    in_window = [0] * len(chosen)
    listens_left = pattern.count(_L) * len(days)

    def behind(i: int) -> bool:
        return any(
            easier.difficulty < chosen[i].difficulty and len(tasks[j]) >= len(tasks[i])
            for j, easier in enumerate(chosen)
        )

    def pick(kind: TaskKind, spoken_today: set[int]) -> int:
        candidates = range(len(chosen))
        if kind is _L:
            return min(
                candidates,
                key=lambda i: (
                    i in covered,
                    not behind(i),
                    in_window[i],
                    -chosen[i].difficulty,
                    -i,
                ),
            )
        if len(chosen) - len(covered) > listens_left:
            return min(candidates, key=lambda i: (i in covered, -chosen[i].difficulty, -i))
        return min(
            candidates,
            key=lambda i: (
                not behind(i),
                i in spoken_today,
                -chosen[i].difficulty,
                in_window[i],
                -i,
            ),
        )

    for day in days:
        spoken_today: set[int] = set()
        for position, kind in enumerate(pattern, start=1):
            m = pick(kind, spoken_today)
            if kind is _L:
                listens_left -= 1
            else:
                spoken_today.add(m)
            tasks[m].append(_Planned(day, _no_speaking_on_first_day(kind, tasks[m], day), position))
            covered.add(m)
            in_window[m] += 1


def _no_speaking_on_first_day(kind: TaskKind, earlier: list[_Planned], day: date) -> TaskKind:
    """`kind`, or Listen if it's Speak on the Milestone's first day (`earlier` is empty
    before `day`): nobody speaks a Scenario before a day of learning its phrases.
    """
    if kind is _S and not any(t.date < day for t in earlier):
        return _L
    return kind


def _choose_scenarios(catalog: tuple[Scenario, ...], ordinary_days: int) -> list[Scenario]:
    """The K most essential Scenarios, ordered easy to hard, then by priority.

    `catalog` comes most essential first, as `scenarios_for` returns it.
    """
    k = min(max(round(ordinary_days / ORDINARY_DAYS_PER_SCENARIO), 2), len(catalog))
    chosen = catalog[:k]
    return sorted(chosen, key=lambda s: (s.difficulty, s.priority))


def _block_lengths(difficulties: list[int], days: int) -> list[int]:
    """Split `days` into one block per Milestone, in proportion to difficulty.

    Largest-remainder apportionment: each block gets the whole part of its exact share,
    and the days left over go to the largest fractional parts, ties going to the harder
    and then the later Milestone. That keeps blocks non-decreasing in difficulty.

    Every block but the last then gets at least one day, taken from the longest block.
    The last is exempt so that a 3-day Plan, with a single ordinary day for 2 Milestones,
    still has its 2 Scenarios: the hardest has an empty block and is first practised in
    the Final Window, where its target date falls.
    """
    total = sum(difficulties)
    shares = [Fraction(days * d, total) for d in difficulties]
    lengths = [floor(share) for share in shares]
    by_remainder = sorted(
        range(len(shares)),
        key=lambda i: (shares[i] - lengths[i], difficulties[i], i),
        reverse=True,
    )
    for i in by_remainder[: days - sum(lengths)]:
        lengths[i] += 1

    while 0 in lengths[:-1]:
        recipient = max(i for i, n in enumerate(lengths[:-1]) if n == 0)
        donor = lengths.index(max(lengths))
        lengths[donor] -= 1
        lengths[recipient] += 1
    return lengths


def _task_minutes(daily_budget: DailyBudget, task_count: int) -> list[int]:
    """Whole minutes for each Task position, sharing what the Review allowance leaves."""
    base, extra = divmod(daily_budget - review_allowance(daily_budget), task_count)
    return [base + 1 if i < extra else base for i in range(task_count)]
