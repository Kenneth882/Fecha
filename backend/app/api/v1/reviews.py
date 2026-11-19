import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_now
from app.core.errors import error_responses
from app.models.user import User
from app.schemas.review import ReviewGrade, ReviewQueue, ReviewResult
from app.services import reviews

router = APIRouter(
    prefix="/events/{event_id}/reviews",
    tags=["reviews"],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)


@router.get("/due")
async def due(
    event_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> ReviewQueue:
    """The Review Queue: the Vocab Items due on local today or earlier, oldest first.
    Empty on the Event Day and for a Past Event."""
    return await reviews.review_queue(session, user, event_id, now)


@router.post("", responses=error_responses(status.HTTP_409_CONFLICT))
async def grade(
    event_id: uuid.UUID,
    data: ReviewGrade,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> ReviewResult:
    """Grade one of today's Reviews: again, hard, good or easy. Returns the item's next
    due date, null once nothing more is scheduled before the Event Day."""
    return await reviews.grade_review(session, user, event_id, data, now)
