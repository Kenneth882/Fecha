"""Stored Milestones refer to Scenarios by slug, with no foreign key (ADR 0003)."""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.catalog import EventType, find_scenario
from tests.auth import register_and_log_in
from tests.conftest import Clock
from tests.events import create_event


async def stored_slugs(db_session: AsyncSession) -> set[str]:
    # A direct DB read: the check is on what's stored, which no endpoint shows whole.
    return set((await db_session.scalars(text("SELECT scenario_slug FROM milestones"))).all())


def missing_from_catalog(slugs: set[str]) -> set[str]:
    return {slug for slug in slugs if find_scenario(slug) is None}


async def test_every_stored_milestone_names_a_scenario_in_the_catalog(
    client: AsyncClient, db_session: AsyncSession, clock: Clock
) -> None:
    for event_type in EventType:
        event_user = await register_and_log_in(client, email=f"{event_type}@example.com")
        # 60 days out: the longest Plan, which covers every Scenario of the type.
        response = await create_event(client, event_user, type=event_type, event_day="2027-01-09")
        assert response.status_code == 201, response.text

    slugs = await stored_slugs(db_session)

    assert {slug.split(".")[0] for slug in slugs} == {t.value for t in EventType}
    assert missing_from_catalog(slugs) == set()


async def test_the_check_catches_a_slug_missing_from_the_catalog(
    db_session: AsyncSession,
) -> None:
    # Guards the guard: an unknown slug must show up as missing.
    assert missing_from_catalog({"interview.salary_negotiation", "interview.gone"}) == {
        "interview.gone"
    }
