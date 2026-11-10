from fastapi import APIRouter, Depends

from app.api.v1 import auth, health
from app.core.deps import get_current_user

# Routes that need no auth: /health and /auth/* (except /auth/me).
public_router = APIRouter(prefix="/api/v1")
public_router.include_router(health.router)
public_router.include_router(auth.router)

# Everything else: each route needs a valid bearer token, so new routes are
# protected by default.
protected_router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])
protected_router.include_router(auth.protected_router)
