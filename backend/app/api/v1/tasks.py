import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_now
from app.core.errors import error_responses
from app.models.user import User
from app.schemas.listen import ListenAnswerCreate, ListenAnswerResult, ListenTask
from app.schemas.task import TaskCompletion, VocabBatch
from app.services import listen_tasks, tasks

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)


@router.get("/{task_id}/vocab")
async def vocab(
    task_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> VocabBatch:
    """A Vocab Task's batch of Vocab Items, in order. The first call fixes it; later
    calls return the same batch. Opening a Task introduces nothing."""
    return await tasks.open_vocab_task(session, user, task_id, now)


@router.post("/{task_id}/complete")
async def complete(
    task_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> TaskCompletion:
    """Complete a Vocab Task, introducing its batch: each item is first due for Review
    the next day. Completing it again changes nothing. A Listen Task is completed by
    answering its questions instead."""
    return await tasks.complete_task(session, user, task_id, now)


@router.get("/{task_id}/listen")
async def listen(
    task_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> ListenTask:
    """A Listen Task's Listen Dialogue and Comprehension Questions, with the answers
    given so far. The first call fixes the dialogue; later calls return the same one.
    A question's correct option is sent only once it's answered."""
    return await listen_tasks.open_listen_task(session, user, task_id, now)


@router.post("/{task_id}/answers")
async def answer(
    task_id: uuid.UUID,
    data: ListenAnswerCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> ListenAnswerResult:
    """Answer one of a Listen Task's Comprehension Questions, for good: the result says
    whether it was right and which option was. The third answer completes the Task."""
    return await listen_tasks.answer_question(session, user, task_id, data, now)
