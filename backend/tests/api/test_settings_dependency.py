from typing import Annotated

from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import Settings
from app.core.deps import get_settings
from app.main import create_app


async def test_routes_receive_the_settings_the_app_was_built_with() -> None:
    custom = Settings(
        jwt_secret=SecretStr("a-non-default-secret-of-at-least-32-bytes"), _env_file=None
    )
    app = create_app(custom)
    seen: list[Settings] = []

    @app.get("/test-only/settings", tags=["test"])
    async def read_settings(settings: Annotated[Settings, Depends(get_settings)]) -> None:
        seen.append(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-only/settings")

    assert response.status_code == 200
    assert seen == [custom]
    assert seen[0] is custom
