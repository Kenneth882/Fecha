import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_now
from app.core.errors import error_responses
from app.models.user import User
from app.schemas.event import EventCreate, EventDetail
from app.services import events

router = APIRouter(
    prefix="/events",
    tags=["events"],
    responses=error_responses(status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT),
)


@router.post(
    "", status_code=status.HTTP_201_CREATED, responses=error_responses(status.HTTP_409_CONFLICT)
)
async def create(
    data: EventCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> EventDetail:
    """Create the User's Event and its first Plan, and return the Event's detail."""
    return await events.create_event(session, user, data, now)


@router.get("/{event_id}", responses=error_responses(status.HTTP_404_NOT_FOUND))
async def get(
    event_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> EventDetail:
    """One of the User's Events, with its state, countdown and Current Plan version."""
    return await events.get_event(session, user, event_id, now)
