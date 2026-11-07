import pytest

from app.core.config import ConfigError, Settings
from app.main import create_app


def test_app_refuses_to_start_without_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)  # ignore any local .env

    with pytest.raises(ConfigError, match="JWT_SECRET"):
        create_app()
