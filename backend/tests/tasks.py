"""Helpers for API tests that open and complete Tasks."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab import VocabItem, VocabSource
from tests.auth import RegisteredUser
from tests.events import EVENTS

TASKS = "/api/v1/tasks"
# Plan Day 1 of the default Event (see test_today.py): two 6-item Vocab Tasks, then two
# Listen Tasks, all for this Scenario.
INTRODUCING_YOURSELF = "interview.introducing_yourself"
WALKING_THROUGH_YOUR_EXPERIENCE = "interview.walking_through_your_experience"


async def add_items(
    session: AsyncSession, scenario_slug: str, count: int, *, prefix: str = ""
) -> list[VocabItem]:
    """`count` Spanish seed Vocab Items for the Scenario, at positions 1..count,
    phrased "frase {prefix}{n}"."""
    items = [
        VocabItem(
            scenario_slug=scenario_slug,
            language="es",
            level=None,
            item_key=f"item_{prefix}{n}",
            phrase=f"frase {prefix}{n}",
            translation=f"phrase {prefix}{n}",
            position=n,
            source=VocabSource.SEED,
        )
        for n in range(1, count + 1)
    ]
    session.add_all(items)
    await session.commit()
    return items


async def tasks_today(
    client: AsyncClient, user: RegisteredUser, event_id: str
) -> list[dict[str, Any]]:
    """The Event's Tasks on the clock's local today, in order."""
    today = await client.get(f"{EVENTS}/{event_id}/today", headers=user.headers)
    tasks: list[dict[str, Any]] = today.json()["tasks"]
    return tasks


def without_request_id(body: dict[str, Any]) -> dict[str, Any]:
    return {"error": {k: v for k, v in body["error"].items() if k != "request_id"}}
