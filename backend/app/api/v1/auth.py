from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_current_user, get_db, get_now, get_settings
from app.core.errors import error_responses
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services import refresh_tokens
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
    now: Annotated[datetime, Depends(get_now)],
) -> TokenResponse:
    """Exchange an email and password for a short-lived access token and a refresh
    token, starting a new session. Needs no auth."""
    user = await authenticate(session, data.email, data.password)
    return await refresh_tokens.issue_for_login(session, user, now, settings)


@router.post("/refresh", responses=error_responses(status.HTTP_401_UNAUTHORIZED))
async def refresh(
    data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
) -> TokenResponse:
    """Swap a refresh token for a new access token and a new refresh token; the one sent
    stops working. Reusing an old one ends every session of its User. Needs no auth."""
    return await refresh_tokens.rotate(session, data.refresh_token, now, settings)


@protected_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(status.HTTP_422_UNPROCESSABLE_CONTENT),
)
async def logout(
    data: RefreshTokenRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    now: Annotated[datetime, Depends(get_now)],
) -> None:
    """End the session the refresh token belongs to, so none of its refresh tokens work
    again. The access token still works until it expires."""
    await refresh_tokens.revoke_family(session, user, data.refresh_token, now)


@protected_router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    """The profile of the User the bearer token names."""
    return UserRead.model_validate(user)
