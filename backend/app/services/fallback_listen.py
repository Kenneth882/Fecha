"""The hand-written fallback Listen Dialogues: reading the committed file and loading it.

The file (`app/data/fallback-listen-es.json`) holds one Listen Dialogue per Scenario,
suited to every Level. A Listen Task uses its Scenario's fallback whenever no generated
dialogue is available, so it never waits for the LLM. `load_fallback_dialogues` makes
the live fallbacks match the file. Like every Listen Dialogue, a fallback is never
edited in place, because Listen Tasks and their answers refer to it: a changed one is
retired and a new row takes its place.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import FALLBACK_LISTEN_ES
from app.models.listen import ListenDialogue, ListenSource
from app.services.catalog import find_scenario
from app.services.listen_content import ListenDialogueContent

# Serialises concurrent loads (two api containers starting at once). It only has to
# differ from the other advisory locks in this database, like the seed vocabulary's.
_ADVISORY_LOCK_ID = 39_000_002


class FallbackListenDialogues(BaseModel):
    """A fallback file: one target language, and one Listen Dialogue per Scenario slug.

    Comprehension Questions are in English, the only Native Language for now.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Annotated[str, StringConstraints(min_length=2, max_length=8)]
    dialogues: dict[str, ListenDialogueContent]

    @model_validator(mode="after")
    def _slugs_are_in_the_catalog(self) -> Self:
        for slug in self.dialogues:
            if find_scenario(slug) is None:
                raise ValueError(f"{slug!r} is not in the Scenario Catalog")
        return self


def read_fallback_dialogues(path: Path = FALLBACK_LISTEN_ES) -> FallbackListenDialogues:
    """Parse and validate a fallback file. Raises pydantic's ValidationError if it's
    invalid, including when a dialogue fails the Listen Dialogue checks."""
    return FallbackListenDialogues.model_validate_json(path.read_bytes())


class FallbackListenLoad(BaseModel):
    """What one `load_fallback_dialogues` run changed. All zeros means nothing changed."""

    inserted: int
    replaced: int
    retired: int


async def load_fallback_dialogues(
    session: AsyncSession, fallbacks: FallbackListenDialogues, now: datetime
) -> FallbackListenLoad:
    """Make the live fallbacks for `fallbacks.language` match the file, and commit.

    Idempotent: a second run with the same file changes nothing. A Scenario with no
    live fallback gets one. One whose dialogue changed has the old row retired at
    `now` and a new one inserted. A live fallback whose Scenario left the file is
    retired. Generated dialogues are never touched.
    """
    await session.execute(select(func.pg_advisory_xact_lock(_ADVISORY_LOCK_ID)))
    live = {
        row.scenario_slug: row
        for row in await session.scalars(
            select(ListenDialogue).where(ListenDialogue.live_fallback(fallbacks.language))
        )
    }
    inserted = replaced = retired = 0
    for slug, content in fallbacks.dialogues.items():
        row = live.pop(slug, None)
        if row is not None and row.content() == content:
            continue
        if row is None:
            inserted += 1
        else:
            row.retired_at = now
            replaced += 1
            # The partial unique index allows one live fallback: retire before inserting.
            await session.flush()
        session.add(
            ListenDialogue.from_content(
                content,
                scenario_slug=slug,
                language=fallbacks.language,
                level=None,
                source=ListenSource.FALLBACK,
                created_at=now,
            )
        )
    for row in live.values():
        row.retired_at = now
        retired += 1
    await session.commit()
    return FallbackListenLoad(inserted=inserted, replaced=replaced, retired=retired)
