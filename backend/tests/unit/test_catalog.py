import pytest
from pydantic import ValidationError

from app.services.catalog import (
    SCENARIO_CATALOG,
    EventType,
    Scenario,
    find_scenario,
    scenarios_for,
)


@pytest.mark.parametrize("event_type", list(EventType))
def test_every_event_type_has_six_scenarios(event_type: EventType) -> None:
    scenarios = scenarios_for(event_type)

    assert len(scenarios) == 6
    assert all(s.event_type is event_type for s in scenarios)


@pytest.mark.parametrize("event_type", list(EventType))
def test_scenarios_come_most_essential_first(event_type: EventType) -> None:
    priorities = [s.priority for s in scenarios_for(event_type)]

    assert priorities == [1, 2, 3, 4, 5, 6]


def test_slugs_are_unique_across_the_catalog() -> None:
    slugs = [s.slug for s in SCENARIO_CATALOG]

    assert len(slugs) == len(set(slugs)) == 18


def test_slugs_are_prefixed_with_their_event_type() -> None:
    for s in SCENARIO_CATALOG:
        assert s.slug.startswith(f"{s.event_type}.")


def test_difficulties_are_between_one_and_three() -> None:
    assert {s.difficulty for s in SCENARIO_CATALOG} <= {1, 2, 3}


def test_a_scenario_is_found_by_its_slug() -> None:
    found = find_scenario("interview.salary_negotiation")

    assert found is not None
    assert found.title == "Salary negotiation"
    assert found.event_type is EventType.INTERVIEW


def test_an_unknown_slug_finds_nothing() -> None:
    assert find_scenario("interview.juggling") is None


def test_a_difficulty_outside_one_to_three_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Scenario(slug="speech.x", event_type=EventType.SPEECH, title="X", difficulty=4, priority=1)
