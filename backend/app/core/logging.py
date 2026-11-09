import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

from app.core.config import LogLevel

# The ID of the request being handled, set by RequestContextMiddleware.
# Every log line written while it's set carries it, not only the access line.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Fields a LogRecord always has. Anything else came from `extra=` and goes into the JSON.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line: timestamp, level, logger, message, request ID and extras."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        entry.update(
            (key, value) for key, value in vars(record).items() if key not in _STANDARD_ATTRS
        )
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _StdoutHandler(logging.StreamHandler[TextIO]):
    """Writes to whatever `sys.stdout` is at emit time, not the one at creation.

    The same trick as the stdlib's `logging.lastResort` uses for stderr, so
    redirecting stdout (as pytest's capsys does) is honoured.
    """

    @property
    def stream(self) -> TextIO:
        return sys.stdout

    @stream.setter
    def stream(self, value: TextIO) -> None:
        pass  # StreamHandler.__init__ assigns it; the property ignores that.


def configure_logging(level: LogLevel) -> None:
    """Send the `app` loggers to stdout as JSON lines, at `level`.

    Safe to call more than once (each `create_app` does): it replaces the handler
    rather than adding another.
    """
    handler = _StdoutHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
