"""The rules a new password must meet. Pure: the common-password set is passed in."""

import string
from collections.abc import Set
from enum import StrEnum

MIN_LENGTH = 8
# NIST SP 800-63B asks for at least 64. 128 characters is at most 512 bytes in UTF-8,
# well under passlib's 4,096-byte limit, beyond which hashing raises instead.
MAX_LENGTH = 128


class PasswordRule(StrEnum):
    """A rule a password can break. Each value doubles as the API error code."""

    TOO_LONG = "password_too_long"
    TOO_SHORT = "password_too_short"
    NO_DIGIT = "password_no_digit"
    NO_SPECIAL_CHARACTER = "password_no_special_character"
    COMMON = "password_too_common"

    @property
    def message(self) -> str:
        return _MESSAGES[self]


_MESSAGES = {
    PasswordRule.TOO_LONG: f"Password must be at most {MAX_LENGTH} characters",
    PasswordRule.TOO_SHORT: f"Password must be at least {MIN_LENGTH} characters",
    PasswordRule.NO_DIGIT: "Password must contain a digit (0-9)",
    PasswordRule.NO_SPECIAL_CHARACTER: (
        "Password must contain a special character (not a letter, digit or space)"
    ),
    PasswordRule.COMMON: "Password is too common; choose one that is harder to guess",
}


def _is_special(char: str) -> bool:
    return not char.isalnum() and not char.isspace()


def broken_password_rule(password: str, common: Set[str]) -> PasswordRule | None:
    """The first rule `password` breaks, in the order listed in PasswordRule, or None.

    `common` holds lowercased passwords; matching against it ignores letter case.
    """
    # First, so an oversized input is rejected before any other rule scans it.
    if len(password) > MAX_LENGTH:
        return PasswordRule.TOO_LONG
    if len(password) < MIN_LENGTH:
        return PasswordRule.TOO_SHORT
    if not any(char in string.digits for char in password):
        return PasswordRule.NO_DIGIT
    if not any(_is_special(char) for char in password):
        return PasswordRule.NO_SPECIAL_CHARACTER
    if password.lower() in common:
        return PasswordRule.COMMON
    return None
