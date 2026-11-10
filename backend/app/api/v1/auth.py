from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.errors import error_responses
from app.schemas.user import UserCreate, UserRead
from app.services.users import register_user

router = APIRouter(prefix="/auth", tags=["auth"], responses=error_responses(422))


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(status.HTTP_409_CONFLICT),
)
async def register(data: UserCreate, session: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    """Create a User and return their profile. Needs no auth."""
    user = await register_user(session, data)
    return UserRead.model_validate(user)
