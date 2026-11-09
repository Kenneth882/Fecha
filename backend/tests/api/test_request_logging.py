import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

LIVENESS = "/api/v1/health"


def log_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    """Every line the app wrote to stdout, each parsed as JSON."""
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


@pytest.fixture
async def http(settings: Settings) -> AsyncIterator[AsyncClient]:
    """A client for an app built from the test settings. Liveness needs no lifespan."""
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_a_request_without_an_id_gets_a_generated_one(http: AsyncClient) -> None:
    first = await http.get(LIVENESS)
    second = await http.get(LIVENESS)

    assert first.headers["X-Request-ID"]
    assert second.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


async def test_a_request_with_an_id_gets_the_same_one_back(http: AsyncClient) -> None:
    response = await http.get(LIVENESS, headers={"X-Request-ID": "trace-abc_123.4"})

    assert response.headers["X-Request-ID"] == "trace-abc_123.4"


@pytest.mark.parametrize(
    "unsafe_id",
    ["x" * 129, 'forged" "status": 500', "a b", "<script>"],
    ids=["too-long", "json-injection", "space", "markup"],
)
async def test_an_unsafe_incoming_id_is_replaced(http: AsyncClient, unsafe_id: str) -> None:
    response = await http.get(LIVENESS, headers={"X-Request-ID": unsafe_id})

    assert response.headers["X-Request-ID"]
    assert response.headers["X-Request-ID"] != unsafe_id


async def test_each_request_writes_one_json_access_line(
    http: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()  # drop anything written while building the app

    response = await http.get(LIVENESS, headers={"X-Request-ID": "trace-1"})

    [line] = log_lines(capsys)
    assert line["request_id"] == "trace-1" == response.headers["X-Request-ID"]
    assert line["method"] == "GET"
    assert line["path"] == LIVENESS
    assert line["status"] == 200
    assert isinstance(line["duration_ms"], float)
    assert line["duration_ms"] >= 0
    assert line["level"] == "INFO"


async def test_the_access_line_carries_the_generated_id(
    http: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    response = await http.get("/api/v1/does-not-exist")

    [line] = log_lines(capsys)
    assert line["request_id"] == response.headers["X-Request-ID"]
    assert line["status"] == 404


async def test_the_log_level_comes_from_the_settings(
    capsys: pytest.CaptureFixture[str], settings: Settings
) -> None:
    app = create_app(settings.model_copy(update={"log_level": "WARNING"}))
    capsys.readouterr()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(LIVENESS)

    assert response.status_code == 200
    assert log_lines(capsys) == []  # the INFO access line is below WARNING


async def test_a_crashing_route_still_returns_and_logs_its_id(
    capsys: pytest.CaptureFixture[str], settings: Settings
) -> None:
    app = create_app(settings)

    @app.get("/test-only/boom", tags=["test"])
    async def boom() -> None:
        raise RuntimeError("boom")

    capsys.readouterr()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-only/boom", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "trace-500"
    [line] = log_lines(capsys)
    assert line["request_id"] == "trace-500"
    assert line["status"] == 500
    assert line["level"] == "ERROR"
    assert "RuntimeError: boom" in line["exc_info"]
