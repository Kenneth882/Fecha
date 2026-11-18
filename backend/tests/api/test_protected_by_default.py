import re

from fastapi import FastAPI
from httpx import AsyncClient

from tests.routes import api_routes

# The only routes callable without a token. Anything added elsewhere must need one.
PUBLIC = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/health/ready"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}


def concrete(path: str) -> str:
    """`path` with any `{param}` filled in, so the request reaches the route."""
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


async def test_every_route_but_the_public_ones_needs_a_token(
    app: FastAPI, client: AsyncClient
) -> None:
    routes = [
        (method, str(route.path)) for route in api_routes(app) for method in route.methods or ()
    ]
    unguarded = []
    for method, path in routes:
        if (method, path) in PUBLIC:
            continue
        response = await client.request(method, concrete(path))
        if response.status_code != 401:
            unguarded.append(f"{method} {path}: {response.status_code}")

    assert unguarded == []
    assert set(routes) >= PUBLIC
    assert {("GET", "/api/v1/auth/me"), ("POST", "/api/v1/auth/logout")} <= set(routes)


async def test_exactly_the_five_public_routes_answer_without_a_token(client: AsyncClient) -> None:
    answered = {
        (method, path)
        for method, path in PUBLIC
        if (await client.request(method, path)).status_code != 401
    }

    assert answered == PUBLIC
    assert len(PUBLIC) == 5
