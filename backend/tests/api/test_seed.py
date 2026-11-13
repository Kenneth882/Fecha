from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.seed import seed_demo
from tests.auth import log_in
from tests.conftest import Clock
from tests.events import EVENTS


async def demo_events(client: AsyncClient, settings: Settings) -> list[Any]:
    """The demo User's Events, as they see them after logging in with the demo
    credentials from settings."""
    logged_in = await log_in(client, settings.demo_email, settings.demo_password.get_secret_value())
    assert logged_in.status_code == 200, logged_in.text
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    response = await client.get(EVENTS, headers=headers)
    assert response.status_code == 200, response.text
    events: list[Any] = response.json()
    for event in events:
        plan = await client.get(f"{EVENTS}/{event['id']}/plan", headers=headers)
        assert plan.status_code == 200, plan.text
        event["plan"] = plan.json()
    return events


async def test_the_demo_user_can_log_in_and_sees_a_spanish_interview_12_days_out(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    # The clock reads 13:00 on 2026-11-10 in Madrid, the demo User's timezone.
    await seed_demo(db_session, settings, clock.now)

    [event] = await demo_events(client, settings)

    assert (event["type"], event["target_language"]) == ("interview", "es")
    assert (event["event_day"], event["state"], event["days_until_event_day"]) == (
        "2026-11-22",
        "active",
        12,
    )
    assert event["plan"]["version"] == 1
    assert event["plan"]["milestones"]


async def test_re_seeding_on_a_later_day_leaves_one_fresh_event_12_days_out(
    client: AsyncClient, db_session: AsyncSession, settings: Settings, clock: Clock
) -> None:
    await seed_demo(db_session, settings, clock.now)
    # Three days later, the 2026-11-22 Event would be only 9 days out.
    clock.now = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
    await seed_demo(db_session, settings, clock.now)

    [event] = await demo_events(client, settings)

    assert (event["event_day"], event["state"], event["days_until_event_day"]) == (
        "2026-11-25",
        "active",
        12,
    )
    assert event["plan"]["version"] == 1
