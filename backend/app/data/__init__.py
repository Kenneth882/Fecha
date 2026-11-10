"""Data files bundled with the app. See README.md in this directory for their sources."""

from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

COMMON_PASSWORD_FILES = (
    DATA_DIR / "common-passwords.txt",
    DATA_DIR / "common-password-patterns.txt",
)


@cache
def common_passwords() -> frozenset[str]:
    """Every bundled common password, lowercased. Read from disk once per process."""
    return frozenset(
        line.strip().lower()
        for path in COMMON_PASSWORD_FILES
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
