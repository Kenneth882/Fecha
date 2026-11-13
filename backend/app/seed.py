"""Recreate the demo User and their Active Event: `uv run python -m app.seed`.

Safe to re-run: each run deletes the demo User (their Events and Plans go with them)
and creates them again, with an Event Day 12 days after their local today, so the
demo never goes stale. The Event goes through the same Event service as
`POST /events`, so its Plan is built by the planner exactly as a real User's is.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, load_settings
from app.db.session import create_engine, create_session_factory
from app.schemas.event import EventCreate, EventDetail
from app.schemas.user import UserCreate
from app.services.catalog import EventType
from app.services.events import create_event
from app.services.local_time import local_today
from app.services.planner import Level
from app.services.users import delete_user_by_email, register_user

DEMO_TIMEZONE = "Europe/Madrid"
DEMO_DAYS_OUT = 12


async def seed_demo(session: AsyncSession, settings: Settings, now: datetime) -> EventDetail:
    """Replace the demo User with a fresh one whose Active Event is a job interview
    in Spanish, `DEMO_DAYS_OUT` days after their local today at `now`."""
    signup = UserCreate(
        email=settings.demo_email,
        password=settings.demo_password.get_secret_value(),
        timezone=DEMO_TIMEZONE,
    )
    # Committed with the new User by register_user.
    await delete_user_by_email(session, signup.email)
    user = await register_user(session, signup)
    return await create_event(
        session,
        user,
        EventCreate(
            type=EventType.INTERVIEW,
            target_language="es",
            event_day=local_today(now, DEMO_TIMEZONE) + timedelta(days=DEMO_DAYS_OUT),
            level=Level.B1,
            daily_budget=30,
            goals="A first-round interview for a customer support role",
        ),
        now,
    )


async def _main() -> None:
    # A composition root, like `create_app` and the worker's startup.
    settings = load_settings()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            event = await seed_demo(session, settings, datetime.now(UTC))
        print(f"Seeded the demo User {settings.demo_email}: Event Day {event.event_day}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
