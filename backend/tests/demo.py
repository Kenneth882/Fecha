"""Helpers for API tests of the seeded demo User."""

from datetime import datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.fallback_listen import load_fallback_dialogues, read_fallback_dialogues
from app.services.seed_vocab import load_seed_vocab, read_seed_vocab
from tests.auth import RegisteredUser, log_in


async def load_seed_content(session: AsyncSession, now: datetime) -> None:
    """What `python -m app.load_seed_vocab` loads: the seed vocabulary and the fallback
    Listen Dialogues, which the demo seed needs."""
    await load_seed_vocab(session, read_seed_vocab(), now)
    await load_fallback_dialogues(session, read_fallback_dialogues(), now)


async def log_in_as_demo(client: AsyncClient, settings: Settings) -> RegisteredUser:
    """The demo User, logged in with the demo credentials from settings."""
    logged_in = await log_in(client, settings.demo_email, settings.demo_password.get_secret_value())
    assert logged_in.status_code == 200, logged_in.text
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"},
    )
    return RegisteredUser(
        profile=me.json(),
        token=logged_in.json()["access_token"],
        refresh_token=logged_in.json()["refresh_token"],
    )
