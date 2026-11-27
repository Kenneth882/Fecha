"""Opening and answering a Listen Task: its Listen Dialogue is fixed on first open, and
answering its third Comprehension Question completes it."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listen import ListenDialogue, ListenSource
from app.services.listen_content import ListenDialogueContent
from tests.auth import RegisteredUser, register_and_log_in
from tests.conftest import FIXED_NOW, Clock
from tests.events import create_event
from tests.tasks import INTRODUCING_YOURSELF, TASKS, tasks_today, without_request_id
from tests.unit.test_listen_dialogue_content import dialogue

TOMORROW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


async def add_fallback(
    session: AsyncSession, scenario_slug: str = INTRODUCING_YOURSELF, **changes: Any
) -> ListenDialogue:
    """The Scenario's live hand-written fallback: `dialogue()` with `changes`."""
    row = ListenDialogue.from_content(
        ListenDialogueContent.model_validate(dialogue(**changes)),
        scenario_slug=scenario_slug,
        language="es",
        level=None,
        source=ListenSource.FALLBACK,
        created_at=FIXED_NOW,
    )
    session.add(row)
    await session.commit()
    return row


async def listen_tasks_today(client: AsyncClient, user: RegisteredUser) -> list[dict[str, Any]]:
    """Create the default Event and return Plan Day 1's two Listen Tasks."""
    event = (await create_event(client, user)).json()
    return [t for t in await tasks_today(client, user, event["id"]) if t["kind"] == "listen"]


async def open_listen(client: AsyncClient, user: RegisteredUser, task_id: str) -> Any:
    response = await client.get(f"{TASKS}/{task_id}/listen", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


def unanswered(number: int, prompt: str, options: list[str]) -> dict[str, Any]:
    return {"number": number, "prompt": prompt, "options": options, "answer": None}


async def test_opening_a_listen_task_shows_its_scenarios_fallback_without_the_answers(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)

    listen = await open_listen(client, user, first["id"])

    assert listen == {
        "task_id": first["id"],
        "status": "pending",
        "answerable": True,
        "speakers": ["Lucía", "Marcos"],
        "lines": dialogue()["lines"],
        "questions": [
            unanswered(1, "Who asks Marcos to sit down?", ["Lucía", "Marcos", "Nobody"]),
            unanswered(2, "How did Marcos get there?", ["By bus", "By metro", "On foot"]),
            unanswered(
                3, "How long did the trip take?", ["Ten minutes", "An hour", "Twenty minutes"]
            ),
        ],
    }


async def test_reopening_shows_the_same_dialogue_even_after_the_fallback_is_replaced(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    fallback = await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)
    opened = await open_listen(client, user, first["id"])
    fallback.retired_at = clock.now
    await add_fallback(
        db_session,
        speakers=["Ana", "Marcos"],
        lines=[
            {**line, "speaker": "Ana" if line["speaker"] == "Lucía" else "Marcos"}
            for line in dialogue()["lines"]
        ],
    )

    assert await open_listen(client, user, first["id"]) == opened


async def test_a_task_opened_after_the_fallback_is_replaced_shows_the_new_one(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    fallback = await add_fallback(db_session)
    first, second = await listen_tasks_today(client, user)
    await open_listen(client, user, first["id"])
    fallback.retired_at = clock.now
    lines = [{**line, "text": f"{line['text']} ¡Hola!"} for line in dialogue()["lines"]]
    await add_fallback(db_session, lines=lines)

    assert (await open_listen(client, user, second["id"]))["lines"] == lines


async def answer(
    client: AsyncClient, user: RegisteredUser, task_id: str, question: int, choice: int
) -> Response:
    return await client.post(
        f"{TASKS}/{task_id}/answers",
        json={"question": question, "choice": choice},
        headers=user.headers,
    )


async def answered(
    client: AsyncClient, user: RegisteredUser, task_id: str, question: int, choice: int
) -> Any:
    response = await answer(client, user, task_id, question, choice)
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_right_answer_says_so_and_names_the_correct_option(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)

    result = await answered(client, user, first["id"], question=2, choice=2)

    assert result == {
        "task_id": first["id"],
        "question": 2,
        "choice": 2,
        "correct": True,
        "correct_option": 2,
        "status": "pending",
    }


async def test_a_wrong_answer_says_so_and_names_the_correct_option(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)

    result = await answered(client, user, first["id"], question=1, choice=3)

    assert (result["correct"], result["correct_option"]) == (False, 1)


async def test_reopening_shows_answered_questions_with_their_answers_and_hides_the_rest(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)
    await answered(client, user, first["id"], question=3, choice=1)

    listen = await open_listen(client, user, first["id"])

    assert [q["answer"] for q in listen["questions"]] == [
        None,
        None,
        {"choice": 1, "correct": False, "correct_option": 3},
    ]
    assert (listen["status"], listen["answerable"]) == ("pending", True)


async def test_answering_the_third_question_completes_the_task_right_or_wrong(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)
    await answered(client, user, first["id"], question=1, choice=1)
    await answered(client, user, first["id"], question=3, choice=1)

    last = await answered(client, user, first["id"], question=2, choice=1)

    assert (last["correct"], last["status"]) == (False, "completed")
    listen = await open_listen(client, user, first["id"])
    assert (listen["status"], listen["answerable"]) == ("completed", False)
    statuses = {t["id"]: t["status"] for t in await tasks_today_of(client, user)}
    assert statuses[first["id"]] == "completed"
    assert await plan_status(client, user, first["id"]) == "completed"


async def plan_status(client: AsyncClient, user: RegisteredUser, task_id: str) -> str:
    """The Task's status in its Event's Plan view."""
    [event] = (await client.get("/api/v1/events", headers=user.headers)).json()
    plan = (await client.get(f"/api/v1/events/{event['id']}/plan", headers=user.headers)).json()
    [status] = [
        task["status"]
        for milestone in plan["milestones"]
        for day in milestone["days"]
        for task in day["tasks"]
        if task["id"] == task_id
    ]
    return str(status)


async def tasks_today_of(client: AsyncClient, user: RegisteredUser) -> list[dict[str, Any]]:
    events = (await client.get("/api/v1/events", headers=user.headers)).json()
    return await tasks_today(client, user, events[0]["id"])


async def test_answering_before_opening_fixes_the_dialogue_too(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    fallback = await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)
    await answered(client, user, first["id"], question=1, choice=1)
    fallback.retired_at = clock.now
    await add_fallback(
        db_session,
        lines=[{**line, "text": f"{line['text']} ¡Hola!"} for line in dialogue()["lines"]],
    )

    assert (await open_listen(client, user, first["id"]))["lines"] == dialogue()["lines"]


async def test_answering_a_question_twice_is_a_409_and_keeps_the_first_answer(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)
    await answered(client, user, first["id"], question=1, choice=2)

    response = await answer(client, user, first["id"], question=1, choice=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "question_already_answered"
    listen = await open_listen(client, user, first["id"])
    assert listen["questions"][0]["answer"] == {"choice": 2, "correct": False, "correct_option": 1}


@pytest.mark.parametrize(("question", "choice"), [(0, 1), (4, 1), (1, 0), (1, 4)])
async def test_a_question_or_choice_out_of_range_is_a_422(
    client: AsyncClient,
    user: RegisteredUser,
    clock: Clock,
    db_session: AsyncSession,
    question: int,
    choice: int,
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)

    response = await answer(client, user, first["id"], question, choice)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_answering_a_missed_task_is_a_409_and_it_stays_read_only(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)
    clock.now = TOMORROW

    response = await answer(client, user, first["id"], question=1, choice=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_missed"
    listen = await open_listen(client, user, first["id"])
    assert (listen["status"], listen["answerable"]) == ("missed", False)
    assert listen["lines"] == dialogue()["lines"]
    assert [q["answer"] for q in listen["questions"]] == [None, None, None]


async def test_answering_a_task_of_a_later_plan_day_is_a_409_until_that_day(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    # Plan Day 2 (2026-11-11) has a Listen Task for this Scenario.
    await add_fallback(db_session, "interview.walking_through_your_experience")
    event = (await create_event(client, user)).json()
    clock.now = TOMORROW
    [tomorrow] = [t for t in await tasks_today(client, user, event["id"]) if t["kind"] == "listen"]
    clock.now = FIXED_NOW

    response = await answer(client, user, tomorrow["id"], question=1, choice=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_in_future"
    assert (await open_listen(client, user, tomorrow["id"]))["answerable"] is False
    clock.now = TOMORROW
    assert (await answer(client, user, tomorrow["id"], question=1, choice=1)).status_code == 200


async def test_answering_a_task_of_a_past_event_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    event = (await create_event(client, user)).json()
    first = next(t for t in await tasks_today(client, user, event["id"]) if t["kind"] == "listen")
    abandoned = await client.post(f"/api/v1/events/{event['id']}/abandon", headers=user.headers)
    assert abandoned.status_code == 200

    response = await answer(client, user, first["id"], question=1, choice=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_already_past"
    assert (await open_listen(client, user, first["id"]))["answerable"] is False


async def test_completing_a_listen_task_directly_is_a_409(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession
) -> None:
    await add_fallback(db_session)
    first, _ = await listen_tasks_today(client, user)

    response = await client.post(f"{TASKS}/{first['id']}/complete", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "completed_by_answering"


@pytest.mark.parametrize(("kind", "now"), [("vocab", FIXED_NOW), ("speak", TOMORROW)])
@pytest.mark.parametrize("action", ["open", "answer"])
async def test_vocab_and_speak_tasks_are_a_409(
    client: AsyncClient,
    user: RegisteredUser,
    clock: Clock,
    db_session: AsyncSession,
    kind: str,
    now: datetime,
    action: str,
) -> None:
    event = (await create_event(client, user)).json()
    clock.now = now
    [task, *_] = [t for t in await tasks_today(client, user, event["id"]) if t["kind"] == kind]

    response = await send(client, user, action, task["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_a_listen_task"


async def send(client: AsyncClient, user: RegisteredUser, action: str, task_id: str) -> Response:
    if action == "open":
        return await client.get(f"{TASKS}/{task_id}/listen", headers=user.headers)
    return await answer(client, user, task_id, question=1, choice=1)


@pytest.mark.parametrize("action", ["open", "answer"])
async def test_another_users_task_is_a_404_identical_to_an_unknown_id(
    client: AsyncClient, user: RegisteredUser, clock: Clock, db_session: AsyncSession, action: str
) -> None:
    await add_fallback(db_session)
    other = await register_and_log_in(client, email="other@example.com")
    theirs, _ = await listen_tasks_today(client, other)

    for_theirs = await send(client, user, action, theirs["id"])
    for_unknown = await send(client, user, action, str(uuid.uuid4()))

    assert for_theirs.status_code == for_unknown.status_code == 404
    assert without_request_id(for_theirs.json()) == without_request_id(for_unknown.json())
    assert for_theirs.json()["error"]["code"] == "task_not_found"
