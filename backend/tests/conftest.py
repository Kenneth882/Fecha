import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long"

# app.main builds the app at import time, which needs a JWT secret.
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret=SecretStr(TEST_JWT_SECRET), _env_file=None)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
