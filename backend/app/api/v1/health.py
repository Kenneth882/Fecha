from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def liveness() -> HealthResponse:
    """Answers while the process is up. Checks no dependencies and needs no auth."""
    return HealthResponse(status="ok")
