"""Opening and answering a User's Listen Tasks.

A Listen Task's Listen Dialogue is fixed the first time it's opened or answered, and
stored on the Task, so it's the same every time. For now that's always its Scenario's
hand-written fallback; generated dialogues come with #69. Each Comprehension Question
takes one final answer, and the third answer completes the Task in the same
transaction. Every fix and answer takes the Event's lock first (`lock_event`).
"""

import uuid
from datetime import datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.event import Event, Task
from app.models.listen import ListenAnswer, ListenDialogue
from app.models.user import User
from app.schemas.listen import (
    GivenAnswer,
    ListenAnswerCreate,
    ListenAnswerResult,
    ListenLine,
    ListenQuestion,
    ListenTask,
)
from app.services.listen_content import QUESTION_COUNT
from app.services.local_time import local_today
from app.services.planner import TaskKind
from app.services.task_status import TaskStatus, task_status
from app.services.tasks import can_complete, check_completable, lock_event, own_task


class NotAListenTaskError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "not_a_listen_task"
    message = "Only Listen Tasks have a Listen Dialogue and Comprehension Questions"


class QuestionAlreadyAnsweredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "question_already_answered"
    message = "This Comprehension Question is already answered, and an answer is final"


async def open_listen_task(
    session: AsyncSession, user: User, task_id: uuid.UUID, now: datetime
) -> ListenTask:
    """One of the User's Listen Tasks, fixing its Listen Dialogue if this is the first
    open, with the answers given so far.

    A Task that can no longer be completed (Missed, or a Past Event's) is read-only: it
    shows the dialogue fixed before, or else the one it would get, without fixing it.
    Raises TaskNotFoundError if there's no such Task or it's another User's, and
    NotAListenTaskError for a Vocab or Speak Task.
    """
    task, event, scenario_slug = await _own_listen_task(session, user, task_id)
    today = local_today(now, user.timezone)
    if task.listen_dialogue_id is None:
        await lock_event(session, event, task)
        if task.listen_dialogue_id is None and can_complete(task, event, today):
            await _fix_dialogue(session, task, event, scenario_slug, now)
            await session.commit()
    if task.listen_dialogue_id is None:
        dialogue = await _choose_dialogue(session, event, scenario_slug)
    else:
        dialogue = await _fixed_dialogue(session, task)
    answers = await _answers(session, task)
    content = dialogue.content()
    status_today = task_status(task.date, task.completed_at, today=today)
    return ListenTask(
        task_id=task.id,
        status=status_today,
        answerable=status_today is TaskStatus.PENDING
        and task.date == today
        and can_complete(task, event, today),
        speakers=content.speakers,
        lines=[ListenLine(speaker=line.speaker, text=line.text) for line in content.lines],
        questions=[
            ListenQuestion(
                number=number,
                prompt=question.prompt,
                options=question.options,
                answer=_given(answers[number], question.correct_option)
                if number in answers
                else None,
            )
            for number, question in enumerate(content.questions, start=1)
        ],
    )


async def answer_question(
    session: AsyncSession, user: User, task_id: uuid.UUID, data: ListenAnswerCreate, now: datetime
) -> ListenAnswerResult:
    """Record the User's final answer to one of a Listen Task's Comprehension Questions,
    and complete the Task if it was the last one unanswered. Right and wrong answers
    both count.

    Fixes the Task's Listen Dialogue first if it wasn't fixed yet. Raises
    TaskNotFoundError and NotAListenTaskError as `open_listen_task` does,
    QuestionAlreadyAnsweredError for a question answered before, and, as completing a
    Vocab Task does, EventAlreadyPastError, TaskMissedError and TaskInFutureError.
    """
    task, event, scenario_slug = await _own_listen_task(session, user, task_id)
    await lock_event(session, event, task)
    answers = await _answers(session, task)
    if data.question in answers:
        raise QuestionAlreadyAnsweredError
    check_completable(task, event, local_today(now, user.timezone))
    if task.listen_dialogue_id is None:
        await _fix_dialogue(session, task, event, scenario_slug, now)
        await session.flush()
    dialogue = await _fixed_dialogue(session, task)
    correct_option = dialogue.content().questions[data.question - 1].correct_option
    correct = data.choice == correct_option
    session.add(
        ListenAnswer(
            task_id=task.id,
            question=data.question,
            choice=data.choice,
            is_correct=correct,
            answered_at=now,
        )
    )
    if len(answers) + 1 == QUESTION_COUNT:
        task.completed_at = now
    await session.commit()
    return ListenAnswerResult(
        task_id=task.id,
        question=data.question,
        choice=data.choice,
        correct=correct,
        correct_option=correct_option,
        status=TaskStatus.COMPLETED if task.completed_at is not None else TaskStatus.PENDING,
    )


async def _own_listen_task(
    session: AsyncSession, user: User, task_id: uuid.UUID
) -> tuple[Task, Event, str]:
    """One of the User's Listen Tasks, its Event and its Milestone's Scenario slug."""
    task, event, scenario_slug = await own_task(session, user, task_id)
    if task.kind is not TaskKind.LISTEN:
        raise NotAListenTaskError
    return task, event, scenario_slug


async def _fix_dialogue(
    session: AsyncSession, task: Task, event: Event, scenario_slug: str, now: datetime
) -> None:
    """Choose the Task's Listen Dialogue and store it on the Task, for good."""
    dialogue = await _choose_dialogue(session, event, scenario_slug)
    task.listen_dialogue_id = dialogue.id
    task.listen_dialogue_fixed_at = now


async def _choose_dialogue(
    session: AsyncSession, event: Event, scenario_slug: str
) -> ListenDialogue:
    """The Listen Dialogue a Listen Task of this Scenario would get now: its live
    hand-written fallback in the Event's language.

    Raises LookupError if there's none, which never happens once the fallback file is
    loaded: it covers every Scenario, and a test guards that.
    """
    dialogue = await session.scalar(
        select(ListenDialogue).where(
            ListenDialogue.scenario_slug == scenario_slug,
            ListenDialogue.live_fallback(event.target_language),
        )
    )
    if dialogue is None:
        raise LookupError(
            f"No fallback Listen Dialogue for {scenario_slug!r} in {event.target_language!r}: "
            "run `python -m app.load_seed_vocab`"
        )
    return dialogue


async def _fixed_dialogue(session: AsyncSession, task: Task) -> ListenDialogue:
    """The Listen Dialogue fixed on the Task. It's kept even once retired."""
    dialogue = await session.get(ListenDialogue, task.listen_dialogue_id)
    assert dialogue is not None  # the foreign key
    return dialogue


async def _answers(session: AsyncSession, task: Task) -> dict[int, ListenAnswer]:
    """The Task's answers so far, by question number."""
    rows = await session.scalars(select(ListenAnswer).where(ListenAnswer.task_id == task.id))
    return {row.question: row for row in rows}


def _given(answer: ListenAnswer, correct_option: int) -> GivenAnswer:
    return GivenAnswer(
        choice=answer.choice, correct=answer.is_correct, correct_option=correct_option
    )
