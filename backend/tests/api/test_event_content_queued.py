"""Creating an Event queues its content job once it's committed; a queue failure
doesn't stop the Event being created."""

import json
import uuid

import pytest
from httpx import AsyncClient

from tests.auth import RegisteredUser
from tests.conftest import Clock
from tests.events import EVENTS, create_event
from tests.jobs import FakeJobQueue


async def test_creating_an_event_queues_exactly_one_content_job_for_it(
    client: AsyncClient, user: RegisteredUser, clock: Clock, job_queue: FakeJobQueue
) -> None:
    response = await create_event(client, user)

    assert response.status_code == 201
    assert job_queue.event_content == [uuid.UUID(response.json()["id"])]


async def test_a_rejected_event_queues_nothing(
    client: AsyncClient, user: RegisteredUser, clock: Clock, job_queue: FakeJobQueue
) -> None:
    await create_event(client, user)

    second = await create_event(client, user)

    assert second.status_code == 409
    assert len(job_queue.event_content) == 1


async def test_the_event_is_created_and_the_failure_logged_when_queuing_fails(
    client: AsyncClient,
    user: RegisteredUser,
    clock: Clock,
    job_queue: FakeJobQueue,
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_queue.failing = True
    capsys.readouterr()

    response = await create_event(client, user)

    assert response.status_code == 201
    event_id = response.json()["id"]
    assert (await client.get(f"{EVENTS}/{event_id}", headers=user.headers)).status_code == 200
    logged = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    failures = [line for line in logged if line["level"] == "ERROR"]
    assert len(failures) == 1
    assert failures[0]["event_id"] == event_id
    assert "Redis is down" in failures[0]["exc_info"]
