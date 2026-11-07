from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """The environment doesn't hold a valid configuration, so the app can't start."""


class Settings(BaseSettings):
    """The single source of configuration, read from env vars or an env file."""

    model_config = SettingsConfigDict(
        # Anchored to this file, not the working directory.
        # Later files win: backend/.env overrides the repo-root .env.
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required, no default: the app must never sign tokens with a guessable key.
    jwt_secret: SecretStr = Field(min_length=32)


def load_settings() -> Settings:
    """Read Settings from the environment, turning validation failures into a clear error."""
    try:
        return Settings()
    except ValidationError as exc:
        problems = "\n".join(
            f"  {'.'.join(str(part) for part in error['loc']).upper()}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(
            "Invalid configuration. Set these environment variables "
            f"(or add them to .env; see .env.example):\n{problems}"
        ) from None
