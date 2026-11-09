import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import ConfigError, load_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_settings_refuse_to_load_without_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ConfigError, match="JWT_SECRET"):
        load_settings(env_file=None)


def test_settings_load_from_the_given_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("JWT_SECRET=from-the-env-file-and-at-least-32-bytes\n")

    settings = load_settings(env_file=env_file)

    assert settings.jwt_secret.get_secret_value() == "from-the-env-file-and-at-least-32-bytes"


def test_importing_the_app_module_loads_no_settings() -> None:
    # Make loading settings fail loudly, then import: any import-time
    # composition (e.g. a module-level `app = create_app()`) trips it,
    # whatever .env files exist on this machine.
    probe = (
        "import app.core.config as config\n"
        "def boom(*args, **kwargs):\n"
        "    raise SystemExit('load_settings() called at import time')\n"
        "config.load_settings = boom\n"
        "import app.main\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
