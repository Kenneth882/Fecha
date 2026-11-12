"""The backward planner: from an Event's settings to a draft Plan of Milestones and Tasks.

Pure and deterministic: no clock, no randomness, no I/O. The caller passes the start
date (the User's local today) and gets back plain data, which the Event service stores
as a Plan version.
"""

from datetime import date, timedelta
from enum import StrEnum
from fractions import Fraction
from math import floor
from typing import Literal

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
    VOCAB = "vocab"
    LISTEN = "listen"
    SPEAK = "speak"


class DraftTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    kind: TaskKind
    position: int
    estimated_minutes: int


class DraftMilestone(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_slug: str
    position: int
    target_date: date
    tasks: tuple[DraftTask, ...]


class DraftPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    milestones: tuple[DraftMilestone, ...]


FINAL_WINDOW_DAYS = 2
MIN_PLAN_DAYS = 3

# Minutes of each Daily Budget kept back for the Review Queue, which runs alongside the
# Tasks (Week 3). The Tasks share whatever is left.
_REVIEW_ALLOWANCE: dict[int, int] = {15: 4, 30: 8, 45: 12}

_FIRST_DAY = (TaskKind.VOCAB, TaskKind.VOCAB, TaskKind.LISTEN)
_LATER_DAY = (TaskKind.VOCAB, TaskKind.LISTEN, TaskKind.SPEAK)


def review_allowance(daily_budget: DailyBudget) -> int:
    """Minutes of the Daily Budget kept for Reviews; the Tasks never use them."""
    return _REVIEW_ALLOWANCE[daily_budget]


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
    and its target date is the block's last day. A block opens with Vocab, Vocab, Listen;
    its later days are Vocab, Listen, Speak.

    `level` doesn't change the Plan yet; the Level adjustments arrive with #20, as do the
    Final Window rules. Until then, the Final Window's 2 days extend the last block.

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
    lengths[-1] += FINAL_WINDOW_DAYS
    minutes = _task_minutes(daily_budget, len(_LATER_DAY))

    milestones: list[DraftMilestone] = []
    next_day = start_date
    for position, (scenario, length) in enumerate(zip(chosen, lengths, strict=True), start=1):
        days = [next_day + timedelta(days=i) for i in range(length)]
        next_day += timedelta(days=length)
        tasks = tuple(
            DraftTask(date=d, kind=kind, position=slot, estimated_minutes=minutes[slot - 1])
            for i, d in enumerate(days)
            for slot, kind in enumerate(_FIRST_DAY if i == 0 else _LATER_DAY, start=1)
        )
        milestones.append(
            DraftMilestone(
                scenario_slug=scenario.slug,
                position=position,
                target_date=days[-1],
                tasks=tasks,
            )
        )
    return DraftPlan(milestones=tuple(milestones))


def _choose_scenarios(catalog: tuple[Scenario, ...], ordinary_days: int) -> list[Scenario]:
    """The K most essential Scenarios, ordered easy to hard, then by priority."""
    k = min(max(round(ordinary_days / 2.5), 2), len(catalog))
    chosen = sorted(catalog, key=lambda s: s.priority)[:k]
    return sorted(chosen, key=lambda s: (s.difficulty, s.priority))


def _block_lengths(difficulties: list[int], days: int) -> list[int]:
    """Split `days` into one block per Milestone, in proportion to difficulty.

    Largest-remainder apportionment: each block gets the whole part of its exact share,
    and the days left over go to the largest fractional parts, ties going to the harder
    and then the later Milestone. That keeps blocks non-decreasing in difficulty.

    Every block but the last then gets at least one day, taken from the longest block.
    The last is exempt because the Final Window extends it; that only matters when
    there's a single ordinary day for 2 Milestones.
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
    return [base + 1 if slot < extra else base for slot in range(task_count)]
