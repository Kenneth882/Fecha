"""`load_fallback_dialogues` loads the fallback file into listen_dialogues, idempotently.

A fallback is never edited in place, because Listen Tasks and their answers refer to
it: a changed one is retired and replaced.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listen import ListenDialogue, ListenSource
from app.services.catalog import SCENARIO_CATALOG
from app.services.fallback_listen import (
    FallbackListenDialogues,
    FallbackListenLoad,
    load_fallback_dialogues,
    read_fallback_dialogues,
)
from app.services.listen_content import ListenDialogueContent
from tests.unit.test_listen_dialogue_content import dialogue

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=1)
AIRPORT = "relocation.airport_arrival"
DOCTOR = "relocation.seeing_a_doctor"


def fallbacks(dialogues: dict[str, dict[str, Any]]) -> FallbackListenDialogues:
    return FallbackListenDialogues(
        language="es",
        dialogues={slug: ListenDialogueContent.model_validate(d) for slug, d in dialogues.items()},
    )


async def rows(session: AsyncSession) -> list[tuple[str, str, ListenSource, str, bool]]:
    """(slug, language, source, first line, retired?) of every Listen Dialogue."""
    found = await session.scalars(
        select(ListenDialogue).order_by(ListenDialogue.scenario_slug, ListenDialogue.created_at)
    )
    return [
        (d.scenario_slug, d.language, d.source, d.lines[0]["text"], d.retired_at is not None)
        for d in found
    ]


def renamed(first_line: str) -> dict[str, Any]:
    changed = dialogue()
    changed["lines"][0]["text"] = first_line
    return changed


async def test_loading_inserts_one_live_fallback_per_scenario_suiting_every_level(
    db_session: AsyncSession,
) -> None:
    result = await load_fallback_dialogues(
        db_session, fallbacks({AIRPORT: dialogue(), DOCTOR: renamed("Hola.")}), NOW
    )

    assert result == FallbackListenLoad(inserted=2, replaced=0, retired=0)
    stored = list(await db_session.scalars(select(ListenDialogue)))
    assert {(d.scenario_slug, d.level, d.source) for d in stored} == {
        (AIRPORT, None, ListenSource.FALLBACK),
        (DOCTOR, None, ListenSource.FALLBACK),
    }
    airport = next(d for d in stored if d.scenario_slug == AIRPORT)
    assert airport.content() == ListenDialogueContent.model_validate(dialogue())


async def test_loading_the_same_file_again_changes_nothing(db_session: AsyncSession) -> None:
    await load_fallback_dialogues(db_session, fallbacks({AIRPORT: dialogue()}), NOW)
    before = await rows(db_session)

    result = await load_fallback_dialogues(db_session, fallbacks({AIRPORT: dialogue()}), LATER)

    assert result == FallbackListenLoad(inserted=0, replaced=0, retired=0)
    assert await rows(db_session) == before


async def test_a_changed_fallback_is_retired_and_replaced_not_edited(
    db_session: AsyncSession,
) -> None:
    await load_fallback_dialogues(db_session, fallbacks({AIRPORT: dialogue()}), NOW)

    result = await load_fallback_dialogues(
        db_session, fallbacks({AIRPORT: renamed("Buenas tardes.")}), LATER
    )

    assert result == FallbackListenLoad(inserted=0, replaced=1, retired=0)
    assert await rows(db_session) == [
        (AIRPORT, "es", ListenSource.FALLBACK, dialogue()["lines"][0]["text"], True),
        (AIRPORT, "es", ListenSource.FALLBACK, "Buenas tardes.", False),
    ]


async def test_a_fallback_no_longer_in_the_file_is_retired(db_session: AsyncSession) -> None:
    await load_fallback_dialogues(
        db_session, fallbacks({AIRPORT: dialogue(), DOCTOR: renamed("Hola.")}), NOW
    )

    result = await load_fallback_dialogues(db_session, fallbacks({AIRPORT: dialogue()}), LATER)

    assert result == FallbackListenLoad(inserted=0, replaced=0, retired=1)
    assert (DOCTOR, "es", ListenSource.FALLBACK, "Hola.", True) in await rows(db_session)


async def test_the_committed_file_loads_a_live_fallback_for_every_catalog_scenario(
    db_session: AsyncSession,
) -> None:
    await load_fallback_dialogues(db_session, read_fallback_dialogues(), NOW)

    live = await db_session.scalars(
        select(ListenDialogue.scenario_slug).where(ListenDialogue.retired_at.is_(None))
    )
    assert sorted(live) == sorted(s.slug for s in SCENARIO_CATALOG)
