import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_now
from app.core.errors import error_responses
from app.models.user import User
from app.schemas.task import TaskCompletion, VocabBatch
from app.services import tasks

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
    the next day. Completing it again changes nothing."""
    return await tasks.complete_task(session, user, task_id, now)
