from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from tests.clients import running_client


async def test_readiness_reports_each_dependency_ok_when_both_respond(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


# Port 1 is reserved and nothing listens on it, so connecting is refused at once.
UNREACHABLE_REDIS = SecretStr("redis://127.0.0.1:1/0")
UNREACHABLE_POSTGRES = SecretStr("postgresql+asyncpg://cramplan:cramplan@127.0.0.1:1/cramplan")

# These tests build their own app, with no get_db override: they need the app's own
# session, built from settings, to reach the unreachable database.


async def test_readiness_returns_503_when_redis_is_down(settings: Settings) -> None:
    down = settings.model_copy(update={"redis_url": UNREACHABLE_REDIS})
    async with running_client(create_app(down)) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"postgres": "ok", "redis": "unavailable"},
    }


async def test_readiness_returns_503_when_postgres_is_down(settings: Settings) -> None:
    down = settings.model_copy(update={"database_url": UNREACHABLE_POSTGRES})
    async with running_client(create_app(down)) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"postgres": "unavailable", "redis": "ok"},
    }
