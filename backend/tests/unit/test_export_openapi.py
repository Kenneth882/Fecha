import json
import os
import subprocess
import sys
from pathlib import Path

from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[2]


def export(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the exporter with no app config at all: no secrets, no database, no Redis."""
    bare_env = {"PATH": os.environ["PATH"]}
    return subprocess.run(
        [sys.executable, "-m", "app.export_openapi", *args],
        cwd=BACKEND_DIR,
        env=bare_env,
        capture_output=True,
        text=True,
        check=True,
    )


def test_export_prints_the_apps_openapi_schema_without_config_or_services() -> None:
    schema = json.loads(export().stdout)

    reference = create_app(
        Settings(
            jwt_secret=SecretStr("x" * 32),
            database_url=SecretStr("postgresql+asyncpg://unused/unused"),
            redis_url=SecretStr("redis://unused"),
            _env_file=None,
        )
    ).openapi()
    assert schema == reference
    assert schema["paths"]["/api/v1/health"]["get"]["operationId"] == "health-liveness"


def test_export_writes_the_schema_to_a_file(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"

    export(str(out))

    assert json.loads(out.read_text())["info"]["title"] == "CramPlan API"


def test_export_is_byte_for_byte_stable_across_runs() -> None:
    # CI diffs the generated client, so the same app must give the same bytes.
    assert export().stdout == export().stdout
