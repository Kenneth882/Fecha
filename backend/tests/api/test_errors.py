from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

REGISTER = "/api/v1/auth/register"


async def test_a_validation_error_uses_the_shared_error_body(client: AsyncClient) -> None:
    response = await client.post(
        REGISTER,
        json={
            "email": "ana@example.com",
            "password": "violet-kettle-47-harbor",
            "timezone": "Mars/Base",
        },
        headers={"X-Request-ID": "trace-422"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "The request is invalid",
            "details": [
                {
                    "field": "timezone",
                    "code": "invalid_timezone",
                    "message": "Timezone must be an IANA name, such as Europe/Madrid",
                }
            ],
            "request_id": "trace-422",
        }
    }


async def test_a_validation_error_never_echoes_the_submitted_values(client: AsyncClient) -> None:
    response = await client.post(REGISTER, json={"password": "hunter2-secret", "timezone": 7})

    assert response.status_code == 422
    assert "hunter2-secret" not in response.text


async def test_an_unknown_route_uses_the_shared_error_body(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nope", headers={"X-Request-ID": "trace-404"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "details": [],
            "request_id": "trace-404",
        }
    }


async def test_a_wrong_method_uses_the_shared_error_body(client: AsyncClient) -> None:
    response = await client.get(REGISTER)

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


async def test_an_unhandled_crash_uses_the_shared_error_body_and_hides_the_cause(
    settings: Settings,
) -> None:
    app = create_app(settings)

    @app.get("/test-only/boom", tags=["test"])
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-only/boom", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "details": [],
            "request_id": "trace-500",
        }
    }
