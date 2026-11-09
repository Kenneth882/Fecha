from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env, anchored to this file rather than the working directory.
# Containers don't use it: compose passes config as real env vars.
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class ConfigError(RuntimeError):
    """The environment doesn't hold a valid configuration, so the app can't start."""


class Settings(BaseSettings):
    """The single source of configuration, read from env vars or an env file."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required, no default: the app must never sign tokens with a guessable key.
    jwt_secret: SecretStr = Field(min_length=32)

    # e.g. postgresql+asyncpg://user:password@host:5432/dbname
    database_url: SecretStr
    # e.g. redis://host:6379/0
    redis_url: SecretStr


def load_settings(env_file: Path | None = ROOT_ENV_FILE) -> Settings:
    """Read Settings from env vars plus `env_file` (None: env vars only).

    Call this only from composition roots (`create_app`, the worker's startup,
    `alembic/env.py`); everything else receives Settings as a parameter or dependency.
    Validation failures become a ConfigError naming each missing or invalid variable.
    """
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        problems = "\n".join(
            f"  {'.'.join(str(part) for part in error['loc']).upper()}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(
            "Invalid configuration. Set these environment variables "
            f"(or add them to .env; see .env.example):\n{problems}"
        ) from None
