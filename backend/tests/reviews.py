"""Helpers for API tests of the Review Queue and grading."""

from typing import Any

from httpx import AsyncClient, Response

from tests.auth import RegisteredUser
from tests.events import EVENTS


async def due(client: AsyncClient, user: RegisteredUser, event_id: str) -> Any:
    response = await client.get(f"{EVENTS}/{event_id}/reviews/due", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


async def grade(
    client: AsyncClient, user: RegisteredUser, event_id: str, item_id: str, grade: str
) -> Response:
    return await client.post(
        f"{EVENTS}/{event_id}/reviews",
        json={"vocab_item_id": item_id, "grade": grade},
        headers=user.headers,
    )
