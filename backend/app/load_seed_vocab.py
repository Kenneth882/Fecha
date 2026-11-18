"""Load the seed Vocab Items into the database: `uv run python -m app.load_seed_vocab`.

Safe to re-run: it upserts by (scenario_slug, language, item_key), so a second run
with the same file changes nothing. The api container runs it right after
`alembic upgrade head`, so a fresh database starts with the seed vocabulary.
"""

import asyncio
from datetime import UTC, datetime

from app.core.config import load_settings
from app.db.session import create_engine, create_session_factory
from app.services.seed_vocab import load_seed_vocab, read_seed_vocab


async def _main() -> None:
    # A composition root, like `create_app`, the worker's startup and `app.seed`.
    settings = load_settings()
    seed = read_seed_vocab()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            result = await load_seed_vocab(session, seed, datetime.now(UTC))
        print(
            f"Loaded the {seed.language!r} seed vocabulary: {result.inserted} inserted, "
            f"{result.updated} updated, {result.retired} retired"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
