from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    postgres: CheckStatus
    redis: CheckStatus


class ReadinessResponse(BaseModel):
    status: CheckStatus
    checks: ReadinessChecks
