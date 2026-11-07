from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import Settings
from app.factory import create_app

TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long"


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret=SecretStr(TEST_JWT_SECRET), _env_file=None)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
