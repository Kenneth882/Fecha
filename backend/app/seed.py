"""Recreate the demo User and their Active Event: `uv run python -m app.seed`.

The demo Event already has a history, so a reviewer sees spaced repetition the moment
they log in: their local today is Plan Day 4 of 15, with the Event Day 12 days away.
The seed replays Days 1-3 through the same services the endpoints call, each at noon
of that day: it creates the Event on Day 1, completes each day's Vocab Tasks, and
grades the Review Queue on Days 2 and 3 (mostly Good, some Again). So every Review and
Review State is one the real endpoints could have produced. About 20 Reviews are due
today: a first Review always comes back the next day, so Day 3's new items and Day 2's
items (first reviewed on Day 3) are all due, with the items forgotten on Day 3. Days
1-3's Listen and Speak Tasks show as Missed. Today's Listen Tasks are playable on the
hand-written fallback Listen Dialogues, so the demo needs no Anthropic API key.

Safe to re-run: each run deletes the demo User (their Events, Plans and Reviews go
with them) and replays the history again, ending on the local today at `now`, so the
demo never goes stale. Needs the seed vocabulary and the fallback Listen Dialogues,
both loaded by `python -m app.load_seed_vocab`.
"""

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, load_settings
from app.db.session import create_engine, create_session_factory
from app.models.listen import ListenDialogue
from app.models.user import User
from app.models.vocab import VocabItem
from app.schemas.event import EventCreate, EventDetail
from app.schemas.review import Grade, ReviewGrade
from app.schemas.user import UserCreate
from app.services.catalog import EventType
from app.services.events import create_event, get_event, get_today
from app.services.local_time import local_today
from app.services.planner import Level, TaskKind
from app.services.reviews import grade_review, review_queue
from app.services.tasks import complete_task
from app.services.users import delete_user_by_email, register_user

DEMO_TIMEZONE = "Europe/Madrid"
DEMO_DAYS_OUT = 12
# The Plan Days already done before the local today, which is the next one.
DEMO_DAYS_DONE = 3
# Every this-many-th Review of the history is graded Again; the rest are Good.
AGAIN_EVERY = 10


class SeedVocabMissingError(RuntimeError):
    """The seed content isn't loaded: there are no Spanish Vocab Items for the demo
    Plan's Vocab Tasks to teach, or no fallback Listen Dialogues for its Listen Tasks."""


async def seed_demo(session: AsyncSession, settings: Settings, now: datetime) -> EventDetail:
    """Replace the demo User with a fresh one whose Active Event is a job interview in
    Spanish, `DEMO_DAYS_OUT` days after their local today at `now`, created
    `DEMO_DAYS_DONE` days before it with those days' Vocab Tasks and Reviews done.

    Raises SeedVocabMissingError, changing nothing, if the seed vocabulary or the
    fallback Listen Dialogues aren't loaded.
    """
    if not await _has_spanish_vocab(session):
        raise SeedVocabMissingError(
            "No Spanish Vocab Items to teach: run `python -m app.load_seed_vocab` first"
        )
    if not await _has_spanish_fallbacks(session):
        raise SeedVocabMissingError(
            "No Spanish fallback Listen Dialogues: run `python -m app.load_seed_vocab` first"
        )
    signup = UserCreate(
        email=settings.demo_email,
        password=settings.demo_password.get_secret_value(),
        timezone=DEMO_TIMEZONE,
    )
    # Committed with the new User by register_user.
    await delete_user_by_email(session, signup.email)
    user = await register_user(session, signup)
    today = local_today(now, DEMO_TIMEZONE)
    # The moments the demo User did each of the days before today, oldest first.
    history_noons = [_noon(today - timedelta(days=n)) for n in range(DEMO_DAYS_DONE, 0, -1)]
    event = await create_event(
        session,
        user,
        EventCreate(
            type=EventType.INTERVIEW,
            target_language="es",
            event_day=today + timedelta(days=DEMO_DAYS_OUT),
            level=Level.B1,
            daily_budget=30,
            goals="A first-round interview for a customer support role",
        ),
        history_noons[0],
        # No content job: the demo runs on the hand-written fallbacks, with no API key.
        job_queue=None,
    )
    graded_so_far = 0
    for noon in history_noons:
        graded_so_far = await _clear_review_queue(session, user, event, noon, graded_so_far)
        await _complete_vocab_tasks(session, user, event, noon)
    return await get_event(session, user, event.id, now)


async def _has_spanish_vocab(session: AsyncSession) -> bool:
    return bool(
        await session.scalar(
            select(exists().where(VocabItem.language == "es", VocabItem.retired_at.is_(None)))
        )
    )


async def _has_spanish_fallbacks(session: AsyncSession) -> bool:
    return bool(await session.scalar(select(exists().where(ListenDialogue.live_fallback("es")))))


def _noon(day: date) -> datetime:
    """Noon of `day` in the demo User's timezone, well clear of either midnight."""
    return datetime.combine(day, time(12), ZoneInfo(DEMO_TIMEZONE)).astimezone(UTC)


async def _clear_review_queue(
    session: AsyncSession, user: User, event: EventDetail, now: datetime, graded_so_far: int
) -> int:
    """Grade every Review due at `now`, each AGAIN_EVERY-th of the history Again and
    the rest Good. Returns the Reviews graded so far, counting from `graded_so_far`."""
    queue = await review_queue(session, user, event.id, now)
    for item in queue.items:
        graded_so_far += 1
        grade = Grade.AGAIN if graded_so_far % AGAIN_EVERY == 0 else Grade.GOOD
        await grade_review(
            session, user, event.id, ReviewGrade(vocab_item_id=item.vocab_item_id, grade=grade), now
        )
    return graded_so_far


async def _complete_vocab_tasks(
    session: AsyncSession, user: User, event: EventDetail, now: datetime
) -> None:
    """Complete the Vocab Tasks of the Plan Day at `now`."""
    today = await get_today(session, user, event.id, now)
    for task in today.tasks:
        if task.kind is TaskKind.VOCAB:
            await complete_task(session, user, task.id, now)


async def _main() -> None:
    # A composition root, like `create_app` and the worker's startup.
    settings = load_settings()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            event = await seed_demo(session, settings, datetime.now(UTC))
        print(
            f"Seeded the demo User {settings.demo_email}: Event Day {event.event_day}, "
            f"{event.days_until_event_day} days out"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
