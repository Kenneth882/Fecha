from fastapi import APIRouter

from app.api.v1 import auth, health

# Routes that need no auth: /health and /auth/*. Everything else goes on the
# protected router (added with auth in #7), so new routes are protected by default.
public_router = APIRouter(prefix="/api/v1")
public_router.include_router(health.router)
public_router.include_router(auth.router)
