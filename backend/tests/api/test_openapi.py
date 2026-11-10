from typing import Any

from app.core.config import Settings
from app.main import create_app
from tests.routes import api_routes

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


def operations(settings: Settings) -> list[tuple[str, str, dict[str, Any]]]:
    schema = create_app(settings).openapi()
    return [
        (method.upper(), path, operation)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def test_liveness_operation_id_is_tag_then_route_name(settings: Settings) -> None:
    ids = {(method, path): op["operationId"] for method, path, op in operations(settings)}

    assert ids[("GET", "/api/v1/health")] == "health-liveness"


def test_every_operation_has_exactly_one_tag(settings: Settings) -> None:
    offenders = [
        f"{method} {path}: {op.get('tags', [])}"
        for method, path, op in operations(settings)
        if len(op.get("tags", [])) != 1
    ]

    assert offenders == []


def test_operation_ids_are_unique(settings: Settings) -> None:
    ids = [op["operationId"] for _, _, op in operations(settings)]

    assert len(ids) == len(set(ids)), sorted(ids)


def test_every_operation_id_is_tag_then_route_name(settings: Settings) -> None:
    # Catches routes that bypass the rule with an explicit operation_id=.
    offenders = [
        f"{route.path}: {route.unique_id}"
        for route in api_routes(create_app(settings))
        if route.include_in_schema
        and route.unique_id != f"{route.tags[0] if route.tags else ''}-{route.name}"
    ]

    assert offenders == []


def test_untagged_routes_left_out_of_the_schema_do_not_break_the_app(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/internal-only", include_in_schema=False)
    async def internal_only() -> None: ...

    assert "/internal-only" not in app.openapi()["paths"]


def test_register_operation_id_is_tag_then_route_name(settings: Settings) -> None:
    ids = {(method, path): op["operationId"] for method, path, op in operations(settings)}

    assert ids[("POST", "/api/v1/auth/register")] == "auth-register"


# Readiness reports which dependency is down in its 503; it's a health report, not an
# error, and load balancers only read the status code.
NOT_ERROR_BODIES = {("GET", "/api/v1/health/ready", "503")}


def test_every_documented_error_response_uses_the_shared_error_body(settings: Settings) -> None:
    error_ref = "#/components/schemas/ErrorResponse"
    offenders = [
        f"{method} {path} {code}: {body}"
        for method, path, op in operations(settings)
        for code, response in op["responses"].items()
        if code.startswith(("4", "5")) and (method, path, code) not in NOT_ERROR_BODIES
        for body in [response.get("content", {}).get("application/json", {}).get("schema")]
        if body != {"$ref": error_ref}
    ]

    assert offenders == []


def test_register_documents_its_409_and_422(settings: Settings) -> None:
    [register] = [op for _, path, op in operations(settings) if path == "/api/v1/auth/register"]

    assert {"409", "422"} <= set(register["responses"])


def test_login_and_me_operation_ids_are_tag_then_route_name(settings: Settings) -> None:
    ids = {(method, path): op["operationId"] for method, path, op in operations(settings)}

    assert ids[("POST", "/api/v1/auth/login")] == "auth-login"
    assert ids[("GET", "/api/v1/auth/me")] == "auth-me"


def test_login_documents_401_and_422_and_me_documents_401(settings: Settings) -> None:
    by_route = {(method, path): op for method, path, op in operations(settings)}

    assert {"401", "422"} <= set(by_route[("POST", "/api/v1/auth/login")]["responses"])
    assert "401" in by_route[("GET", "/api/v1/auth/me")]["responses"]


def test_me_declares_bearer_auth_so_the_generated_client_sends_the_token(
    settings: Settings,
) -> None:
    by_route = {(method, path): op for method, path, op in operations(settings)}

    assert by_route[("GET", "/api/v1/auth/me")]["security"] == [{"HTTPBearer": []}]
