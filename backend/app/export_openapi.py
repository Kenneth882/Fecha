"""Print the API's OpenAPI schema without running the server.

`uv run python -m app.export_openapi [PATH]`: with PATH it writes the schema there,
otherwise to stdout. The web app's TypeScript client is generated from this output
(`npm run generate:api` in `web/`).

It needs no config, database or Redis. It isn't a composition root and doesn't call
`load_settings()`: the schema doesn't depend on any setting, so it builds the app
with placeholder Settings, and `create_app` connects to nothing until its lifespan
starts, which never happens here.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

# Never used to sign or connect to anything: the app is built, asked for its
# schema and thrown away.
_PLACEHOLDER_SETTINGS = Settings(
    jwt_secret=SecretStr("openapi-export-placeholder-not-a-secret"),
    database_url=SecretStr("postgresql+asyncpg://unused/unused"),
    redis_url=SecretStr("redis://unused"),
    log_level="WARNING",
    _env_file=None,
)


def openapi_schema() -> dict[str, Any]:
    return create_app(_PLACEHOLDER_SETTINGS).openapi()


def render(schema: dict[str, Any]) -> str:
    """Stable text for the schema, so regenerating an unchanged API changes no bytes."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> None:
    text = render(openapi_schema())
    if argv:
        Path(argv[0]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main(sys.argv[1:])
