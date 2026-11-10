from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.models.user import User
from tests.auth import RegisteredUser

ADMIN_ONLY = "/test-only/admin"


@pytest.fixture(autouse=True)
def admin_only_route(app: FastAPI) -> None:
    """No real route needs an admin yet, so the tests add one."""

    @app.get(ADMIN_ONLY, tags=["test"])
    async def admin_only(admin: Annotated[User, Depends(require_admin)]) -> dict[str, str]:
        return {"admin": str(admin.id)}


async def test_a_non_admin_user_gets_403(client: AsyncClient, user: RegisteredUser) -> None:
    response = await client.get(ADMIN_ONLY, headers=user.headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_required"


async def test_an_admin_user_gets_through(
    client: AsyncClient, user: RegisteredUser, db_session: AsyncSession
) -> None:
    # No API grants the admin role, by design, so it's set directly.
    await db_session.execute(
        text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user.profile["id"]}
    )
    db_session.expire_all()

    response = await client.get(ADMIN_ONLY, headers=user.headers)

    assert response.status_code == 200
    assert response.json() == {"admin": user.profile["id"]}


async def test_no_token_gets_401_not_403(client: AsyncClient) -> None:
    response = await client.get(ADMIN_ONLY)

    assert response.status_code == 401
