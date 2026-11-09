from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import ROOT_ENV_FILE, Settings
from app.core.deps import get_db
from app.main import create_app
from tests.clients import running_client
from tests.db.fixtures import build_test_schema, transactional_session

TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long"


class TestEnv(BaseSettings):
    """Where the test services live: env vars, else the repo-root .env (see .env.example)."""

    __test__ = False  # not a pytest test class

    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    test_database_url: SecretStr
    redis_url: SecretStr


@pytest.fixture(scope="session")
def test_env() -> TestEnv:
    return TestEnv()


@pytest.fixture(scope="session")
async def test_engine(test_env: TestEnv) -> AsyncIterator[AsyncEngine]:
    """The test database engine. The schema is rebuilt from the migrations once per run."""
    engine = create_async_engine(test_env.test_database_url.get_secret_value())
    await build_test_schema(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """This test's session. Everything it writes is rolled back afterwards."""
    async with transactional_session(test_engine) as session:
        yield session


@pytest.fixture
def settings(test_env: TestEnv) -> Settings:
    return Settings(
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        database_url=test_env.test_database_url,
        redis_url=test_env.redis_url,
        _env_file=None,
    )


@pytest.fixture
async def client(settings: Settings, db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """A client for the app, with its lifespan run and `get_db` swapped for `db_session`."""
    app = create_app(settings)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with running_client(app) as client:
        yield client
