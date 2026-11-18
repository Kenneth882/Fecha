"""`load_seed_vocab` upserts the seed file into vocab_items, idempotently."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab import GENERATED_KEY_PREFIX, VocabItem, VocabSource
from app.services.catalog import SCENARIO_CATALOG
from app.services.seed_vocab import (
    SeedVocab,
    SeedVocabItem,
    SeedVocabLoad,
    load_seed_vocab,
    read_seed_vocab,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
AIRPORT = "relocation.airport_arrival"
DOCTOR = "relocation.seeing_a_doctor"

HELLO = SeedVocabItem(item_key="hello", phrase="Hola.", translation="Hello.")
EXIT = SeedVocabItem(
    item_key="exit", phrase="¿Dónde está la salida?", translation="Where's the exit?"
)
HURTS = SeedVocabItem(item_key="it_hurts", phrase="Me duele aquí.", translation="It hurts here.")

NOTHING_CHANGED = SeedVocabLoad(inserted=0, updated=0, retired=0)


def seed(scenarios: dict[str, list[SeedVocabItem]]) -> SeedVocab:
    return SeedVocab(language="es", scenarios=scenarios)


Row = tuple[str, str, str, str, str, int, VocabSource, datetime | None]


async def vocab_rows(session: AsyncSession) -> list[Row]:
    items = await session.scalars(
        select(VocabItem).order_by(VocabItem.scenario_slug, VocabItem.position, VocabItem.item_key)
    )
    return [
        (
            i.scenario_slug,
            i.language,
            i.item_key,
            i.phrase,
            i.translation,
            i.position,
            i.source,
            i.retired_at,
        )
        for i in items
    ]


async def test_loading_inserts_each_item_at_its_position_in_the_file(
    db_session: AsyncSession,
) -> None:
    result = await load_seed_vocab(db_session, seed({AIRPORT: [HELLO, EXIT], DOCTOR: [HURTS]}), NOW)

    assert result == SeedVocabLoad(inserted=3, updated=0, retired=0)
    assert await vocab_rows(db_session) == [
        (AIRPORT, "es", "hello", "Hola.", "Hello.", 1, VocabSource.SEED, None),
        (
            AIRPORT,
            "es",
            "exit",
            "¿Dónde está la salida?",
            "Where's the exit?",
            2,
            VocabSource.SEED,
            None,
        ),
        (DOCTOR, "es", "it_hurts", "Me duele aquí.", "It hurts here.", 1, VocabSource.SEED, None),
    ]


async def test_loading_the_same_file_twice_changes_nothing(db_session: AsyncSession) -> None:
    file = seed({AIRPORT: [HELLO, EXIT], DOCTOR: [HURTS]})
    await load_seed_vocab(db_session, file, NOW)
    before = await vocab_rows(db_session)

    result = await load_seed_vocab(db_session, file, NOW + timedelta(days=1))

    assert result == NOTHING_CHANGED
    assert await vocab_rows(db_session) == before


async def test_loading_the_real_seed_file_twice_changes_nothing(db_session: AsyncSession) -> None:
    first = await load_seed_vocab(db_session, read_seed_vocab(), NOW)
    before = await vocab_rows(db_session)

    second = await load_seed_vocab(db_session, read_seed_vocab(), NOW + timedelta(days=1))

    assert first.inserted == len(before) and first.retired == 0
    assert second == NOTHING_CHANGED
    assert await vocab_rows(db_session) == before


async def test_after_loading_every_catalog_scenario_has_at_least_12_live_spanish_items(
    db_session: AsyncSession,
) -> None:
    await load_seed_vocab(db_session, read_seed_vocab(), NOW)

    live = [row for row in await vocab_rows(db_session) if row[7] is None and row[1] == "es"]
    for scenario in SCENARIO_CATALOG:
        assert sum(row[0] == scenario.slug for row in live) >= 12, scenario.slug


async def test_an_item_removed_from_the_file_is_retired_not_deleted(
    db_session: AsyncSession,
) -> None:
    await load_seed_vocab(db_session, seed({AIRPORT: [HELLO, EXIT]}), NOW)
    later = NOW + timedelta(days=1)

    result = await load_seed_vocab(db_session, seed({AIRPORT: [EXIT]}), later)

    assert result == SeedVocabLoad(inserted=0, updated=1, retired=1)  # exit moved to position 1
    assert await vocab_rows(db_session) == [
        (
            AIRPORT,
            "es",
            "exit",
            "¿Dónde está la salida?",
            "Where's the exit?",
            1,
            VocabSource.SEED,
            None,
        ),
        (AIRPORT, "es", "hello", "Hola.", "Hello.", 1, VocabSource.SEED, later),
    ]


async def test_a_retired_item_stays_retired_from_the_first_time_it_left(
    db_session: AsyncSession,
) -> None:
    await load_seed_vocab(db_session, seed({AIRPORT: [EXIT, HELLO]}), NOW)
    await load_seed_vocab(db_session, seed({AIRPORT: [EXIT]}), NOW + timedelta(days=1))

    result = await load_seed_vocab(db_session, seed({AIRPORT: [EXIT]}), NOW + timedelta(days=2))

    assert result == NOTHING_CHANGED
    [_, hello] = await vocab_rows(db_session)
    assert hello[7] == NOW + timedelta(days=1)


async def test_an_item_put_back_in_the_file_is_un_retired(db_session: AsyncSession) -> None:
    await load_seed_vocab(db_session, seed({AIRPORT: [EXIT, HELLO]}), NOW)
    await load_seed_vocab(db_session, seed({AIRPORT: [EXIT]}), NOW + timedelta(days=1))

    result = await load_seed_vocab(db_session, seed({AIRPORT: [EXIT, HELLO]}), NOW)

    assert result == SeedVocabLoad(inserted=0, updated=1, retired=0)
    assert [row[7] for row in await vocab_rows(db_session)] == [None, None]


async def test_editing_a_phrase_updates_it_in_place(db_session: AsyncSession) -> None:
    await load_seed_vocab(db_session, seed({AIRPORT: [HELLO]}), NOW)
    [before] = await db_session.scalars(select(VocabItem.id))

    edited = HELLO.model_copy(update={"phrase": "¡Hola!", "translation": "Hi!"})
    result = await load_seed_vocab(db_session, seed({AIRPORT: [edited]}), NOW)

    assert result == SeedVocabLoad(inserted=0, updated=1, retired=0)
    [item] = await db_session.scalars(select(VocabItem))
    assert (item.id, item.phrase, item.translation) == (before, "¡Hola!", "Hi!")


async def test_loading_never_retires_generated_items(db_session: AsyncSession) -> None:
    db_session.add(
        VocabItem(
            scenario_slug=AIRPORT,
            language="es",
            level=None,
            item_key=f"{GENERATED_KEY_PREFIX}gate",
            phrase="¿Cuál es mi puerta de embarque?",
            translation="Which is my boarding gate?",
            position=21,
            source=VocabSource.GENERATED,
        )
    )
    await db_session.commit()

    result = await load_seed_vocab(db_session, seed({AIRPORT: [HELLO]}), NOW)

    assert result == SeedVocabLoad(inserted=1, updated=0, retired=0)
    assert all(row[7] is None for row in await vocab_rows(db_session))


async def test_a_scenario_language_and_key_can_only_be_stored_once(
    db_session: AsyncSession,
) -> None:
    await load_seed_vocab(db_session, seed({AIRPORT: [HELLO]}), NOW)
    db_session.add(
        VocabItem(
            scenario_slug=AIRPORT,
            language="es",
            level=None,
            item_key="hello",
            phrase="Buenas.",
            translation="Hi.",
            position=2,
            source=VocabSource.GENERATED,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
