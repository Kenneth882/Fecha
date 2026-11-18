"""The hand-written seed vocabulary: reading the committed file and loading it.

The file (`app/data/seed-vocab-es.json`) is the source of truth for seed Vocab Items.
`load_seed_vocab` upserts it into `vocab_items` by (scenario_slug, language, item_key),
so editing a phrase is a one-line change to the file with no migration. Seed items
that leave the file are retired, never deleted, because Review States and Reviews
refer to them.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import SEED_VOCAB_ES
from app.models.vocab import GENERATED_KEY_PREFIX, VocabItem, VocabSource
from app.services.catalog import find_scenario

# Stable forever once shipped, like a Scenario slug: Review States refer to the item.
ItemKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Serialises concurrent loads (two api containers starting at once). Any constant
# bigint will do; it only has to differ from other advisory locks in this database.
_ADVISORY_LOCK_ID = 39_000_001


class SeedVocabItem(BaseModel):
    """One phrase in the seed file. Its position is its place in the Scenario's list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_key: ItemKey
    phrase: NonBlankText
    translation: NonBlankText

    @field_validator("item_key")
    @classmethod
    def _key_is_not_a_generated_key(cls, key: str) -> str:
        if key.startswith(GENERATED_KEY_PREFIX):
            raise ValueError(
                f"{key!r}: keys starting {GENERATED_KEY_PREFIX!r} are for generated items"
            )
        return key


class SeedVocab(BaseModel):
    """A seed file: one target language, its items per Scenario slug, easiest first.

    Translations are in English, the only Native Language for now.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Annotated[str, StringConstraints(min_length=2, max_length=8)]
    scenarios: dict[str, list[SeedVocabItem]]

    @model_validator(mode="after")
    def _slugs_and_keys_are_valid(self) -> Self:
        for slug, items in self.scenarios.items():
            if find_scenario(slug) is None:
                raise ValueError(f"{slug!r} is not in the Scenario Catalog")
            seen: set[str] = set()
            for item in items:
                if item.item_key in seen:
                    raise ValueError(f"{slug!r} has the item_key {item.item_key!r} twice")
                seen.add(item.item_key)
        return self


def read_seed_vocab(path: Path = SEED_VOCAB_ES) -> SeedVocab:
    """Parse and validate a seed file. Raises pydantic's ValidationError if it's invalid."""
    return SeedVocab.model_validate_json(path.read_bytes())


class SeedVocabLoad(BaseModel):
    """What one `load_seed_vocab` run changed. All zeros means nothing changed."""

    inserted: int
    updated: int
    retired: int


async def load_seed_vocab(session: AsyncSession, seed: SeedVocab, now: datetime) -> SeedVocabLoad:
    """Make the seed rows for `seed.language` match `seed`, and commit.

    Idempotent: a second run with the same file changes nothing. An item in the file
    is inserted, or updated if its phrase, translation or position changed (and
    un-retired if it had been retired). A seed item of this language that's no longer
    in the file gets `retired_at = now`. Generated items are never touched.
    """
    await session.execute(select(func.pg_advisory_xact_lock(_ADVISORY_LOCK_ID)))
    existing = {
        (row.scenario_slug, row.item_key): row
        for row in await session.scalars(
            select(VocabItem).where(
                VocabItem.language == seed.language, VocabItem.source == VocabSource.SEED
            )
        )
    }
    inserted = updated = retired = 0
    for slug, items in seed.scenarios.items():
        for position, item in enumerate(items, start=1):
            row = existing.pop((slug, item.item_key), None)
            if row is None:
                session.add(
                    VocabItem(
                        scenario_slug=slug,
                        language=seed.language,
                        level=None,
                        item_key=item.item_key,
                        phrase=item.phrase,
                        translation=item.translation,
                        position=position,
                        source=VocabSource.SEED,
                    )
                )
                inserted += 1
            elif (row.phrase, row.translation, row.position, row.retired_at) != (
                item.phrase,
                item.translation,
                position,
                None,
            ):
                row.phrase, row.translation, row.position = item.phrase, item.translation, position
                row.retired_at = None
                updated += 1
    for row in existing.values():
        if row.retired_at is None:
            row.retired_at = now
            retired += 1
    await session.commit()
    return SeedVocabLoad(inserted=inserted, updated=updated, retired=retired)
