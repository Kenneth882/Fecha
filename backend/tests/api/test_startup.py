from pathlib import Path

import pytest

from app.core.config import ConfigError
from app.factory import create_app


def test_app_refuses_to_start_without_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env files reachable from here

    with pytest.raises(ConfigError, match="JWT_SECRET"):
        create_app()
