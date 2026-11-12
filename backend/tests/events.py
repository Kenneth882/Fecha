"""Helpers for API tests that create Events."""

import uuid
from typing import Any

from httpx import AsyncClient, Response

from tests.auth import RegisteredUser

EVENTS = "/api/v1/events"


def event_body(**overrides: Any) -> dict[str, Any]:
    """A valid create-Event body, 12 days after 2026-11-10 (the `clock` fixture's
    today in Madrid); keyword arguments replace or add fields."""
    body: dict[str, Any] = {
        "type": "interview",
        "target_language": "es",
        "event_day": "2026-11-22",
        "level": "B1",
        "daily_budget": 30,
        "goals": "A nursing role at a hospital",
    }
    body.update(overrides)
    return body


async def create_event(client: AsyncClient, user: RegisteredUser, **overrides: Any) -> Response:
    return await client.post(EVENTS, json=event_body(**overrides), headers=user.headers)


async def abandon(client: AsyncClient, user: RegisteredUser, event_id: uuid.UUID | str) -> Response:
    return await client.post(f"{EVENTS}/{event_id}/abandon", headers=user.headers)
