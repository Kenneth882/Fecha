from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_current_user, get_db, get_settings
from app.core.errors import error_responses
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import authenticate
from app.services.users import register_user

router = APIRouter(prefix="/auth", tags=["auth"], responses=error_responses(422))
# The /auth routes that need a token, for the protected router.
protected_router = APIRouter(
    prefix="/auth", tags=["auth"], responses=error_responses(status.HTTP_401_UNAUTHORIZED)
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(status.HTTP_409_CONFLICT),
)
async def register(data: UserCreate, session: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    """Create a User and return their profile. Needs no auth."""
    user = await register_user(session, data)
    return UserRead.model_validate(user)


@router.post("/login", responses=error_responses(status.HTTP_401_UNAUTHORIZED))
async def login(
    data: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Exchange an email and password for a short-lived access token. Needs no auth."""
    user = await authenticate(session, data.email, data.password)
    token = create_access_token(user.id, settings)
    return TokenResponse(access_token=token.token, expires_in=token.expires_in)


@protected_router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    """The profile of the User the bearer token names."""
    return UserRead.model_validate(user)
