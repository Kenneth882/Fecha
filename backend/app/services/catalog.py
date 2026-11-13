"""The Scenario Catalog: the fixed, hand-written Scenarios for each Event Type (ADR 0003).

Plain data, no I/O. It's the same in every language. Plans choose and order Scenarios
from it and never make up new ones. A slug is stable forever once shipped: stored
Milestones, and later Vocab Items, refer to Scenarios by it.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    """The kind of Event. It decides which Scenarios are available."""

    INTERVIEW = "interview"
    RELOCATION = "relocation"
    SPEECH = "speech"


# 1 (easy) to 3 (hard).
Difficulty = Annotated[int, Field(ge=1, le=3)]


class Scenario(BaseModel):
    """A reusable real-world situation within an Event Type.

    `difficulty` runs from 1 (easy) to 3 (hard); harder Scenarios get more Plan Days.
    `priority` ranks how essential the Scenario is within its Event Type, 1 being the
    most essential; a Plan too short to cover every Scenario keeps the most essential.
    """

    model_config = ConfigDict(frozen=True)

    slug: str
    event_type: EventType
    title: str
    difficulty: Difficulty
    priority: Annotated[int, Field(ge=1)]


def _scenario(
    event_type: EventType, slug_suffix: str, title: str, difficulty: int, priority: int
) -> Scenario:
    return Scenario(
        slug=f"{event_type}.{slug_suffix}",
        event_type=event_type,
        title=title,
        difficulty=difficulty,
        priority=priority,
    )


_I, _R, _S = EventType.INTERVIEW, EventType.RELOCATION, EventType.SPEECH

SCENARIO_CATALOG: tuple[Scenario, ...] = (
    _scenario(_I, "introducing_yourself", "Introducing yourself", 1, 1),
    _scenario(_I, "walking_through_your_experience", "Walking through your experience", 2, 2),
    _scenario(_I, "why_this_role", "Explaining why you want the role", 2, 3),
    _scenario(_I, "describing_a_challenge", "Describing a challenge you overcame", 3, 4),
    _scenario(_I, "salary_negotiation", "Salary negotiation", 3, 5),
    _scenario(_I, "asking_the_interviewer", "Asking the interviewer questions", 1, 6),
    _scenario(_R, "airport_arrival", "Airport arrival", 1, 1),
    _scenario(_R, "apartment_check_in", "Apartment check-in", 2, 2),
    _scenario(_R, "setting_up_utilities", "Setting up utilities", 2, 3),
    _scenario(_R, "asking_for_help", "Asking for help with a problem", 3, 4),
    _scenario(_R, "opening_a_bank_account", "Opening a bank account", 2, 5),
    _scenario(_R, "seeing_a_doctor", "Seeing a doctor", 3, 6),
    _scenario(_S, "opening_the_speech", "Opening the speech", 1, 1),
    _scenario(_S, "telling_a_personal_story", "Telling a personal story", 2, 2),
    _scenario(_S, "making_your_main_point", "Making your main point", 2, 3),
    _scenario(_S, "closing_and_thanking", "Closing and thanking people", 1, 4),
    _scenario(_S, "answering_audience_questions", "Answering audience questions", 3, 5),
    _scenario(_S, "small_talk_afterwards", "Small talk after the speech", 2, 6),
)

_BY_SLUG = {s.slug: s for s in SCENARIO_CATALOG}


def scenarios_for(event_type: EventType) -> tuple[Scenario, ...]:
    """The Event Type's Scenarios, most essential (lowest `priority`) first."""
    return tuple(
        sorted(
            (s for s in SCENARIO_CATALOG if s.event_type is event_type), key=lambda s: s.priority
        )
    )


def find_scenario(slug: str) -> Scenario | None:
    """The Scenario with this slug, or None if the catalog has no such slug."""
    return _BY_SLUG.get(slug)
