import uuid
import zoneinfo
from datetime import datetime
from functools import cache
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr
from pydantic_core import PydanticCustomError

from app.data import common_passwords
from app.models.user import Role
from app.services.password_policy import broken_password_rule

NativeLanguage = Literal["en"]


@cache
def _iana_timezones() -> frozenset[str]:
    # The tzdata package backs this where the OS has no zoneinfo database (slim images).
    return frozenset(zoneinfo.available_timezones())


def _check_iana_timezone(name: str) -> str:
    if name not in _iana_timezones():
        raise PydanticCustomError(
            "invalid_timezone", "Timezone must be an IANA name, such as Europe/Madrid"
        )
    return name


IanaTimezone = Annotated[str, AfterValidator(_check_iana_timezone)]


def _check_password(password: str) -> str:
    rule = broken_password_rule(password, common_passwords())
    if rule is not None:
        raise PydanticCustomError(rule.value, rule.message)
    return password


NewPassword = Annotated[str, AfterValidator(_check_password)]


# Lowercased whole, so the unique constraint on users.email ignores letter case.
LowercaseEmail = Annotated[EmailStr, AfterValidator(str.lower)]


class UserCreate(BaseModel):
    """What a person sends to register."""

    email: LowercaseEmail
    password: NewPassword
    timezone: IanaTimezone
    native_language: NativeLanguage = "en"


class UserRead(BaseModel):
    """A User's profile. It never carries the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    timezone: str
    native_language: NativeLanguage
    role: Role
    created_at: datetime
