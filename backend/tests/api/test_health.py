from httpx import AsyncClient


async def test_liveness_returns_ok_without_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
