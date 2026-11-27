from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env, anchored to this file rather than the working directory.
# Containers don't use it: compose passes config as real env vars.
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


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
    # How long an access token stays valid. Short, so it never needs revoking; a
    # refresh token gets a new one (ADR 0007).
    access_token_expire_minutes: int = Field(default=30, gt=0)
    # A refresh token's session ends after this many days without a refresh...
    refresh_token_idle_days: int = Field(default=30, gt=0)
    # ...and this many days after its first login, however often it's used.
    refresh_token_absolute_days: int = Field(default=90, gt=0)
    # A refresh token swapped this recently can be used once more without counting as
    # theft, so two tabs or a retry racing one refresh don't end every session. 0 = off.
    refresh_token_reuse_grace_seconds: int = Field(default=30, ge=0)

    # e.g. postgresql+asyncpg://user:password@host:5432/dbname
    database_url: SecretStr
    # e.g. redis://host:6379/0
    redis_url: SecretStr

    # The demo User that `python -m app.seed` recreates. The defaults are documented
    # local placeholders, not secrets: override both anywhere the API is public.
    demo_email: str = "demo@example.com"
    demo_password: SecretStr = SecretStr("local-demo-only-2026!")

    # Level for the app's JSON logs (the per-request access line is INFO).
    log_level: LogLevel = "INFO"

    # Content generation, in the worker. Without a key, generation is off and every
    # Listen Task uses its Scenario's hand-written fallback.
    anthropic_api_key: SecretStr | None = None
    llm_model: str = Field(default="claude-sonnet-5-5", min_length=1)
    # Once the day's LLM calls (UTC) have cost this much, the worker makes no more.
    llm_daily_budget_usd: Decimal = Field(default=Decimal(2), ge=0)

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _blank_key_is_no_key(cls, value: object) -> object:
        """`ANTHROPIC_API_KEY=` (as compose passes an unset one) means no key."""
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def refresh_token_idle(self) -> timedelta:
        return timedelta(days=self.refresh_token_idle_days)

    @property
    def refresh_token_absolute(self) -> timedelta:
        return timedelta(days=self.refresh_token_absolute_days)

    @property
    def refresh_token_reuse_grace(self) -> timedelta:
        return timedelta(seconds=self.refresh_token_reuse_grace_seconds)


def load_settings(env_file: Path | None = ROOT_ENV_FILE) -> Settings:
    """Read Settings from env vars plus `env_file` (None: env vars only).

    Call this only from composition roots (`create_app`, the worker's startup, `app.seed`,
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
