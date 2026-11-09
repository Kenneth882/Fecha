from fastapi import APIRouter

from app.api.v1 import health

# Routes that need no auth: /health now, /auth/* later. Everything else goes on
# the protected router (added with auth in #7), so new routes are protected by default.
public_router = APIRouter(prefix="/api/v1")
public_router.include_router(health.router)
