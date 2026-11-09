import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

# Incoming IDs end up in logs, so only short IDs from a safe alphabet are trusted.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")

access_logger = logging.getLogger("app.access")


def _request_id(scope: Scope) -> str:
    """The caller's X-Request-ID if it's safe to log, else a fresh one."""
    incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
    if incoming is not None and _SAFE_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


class RequestContextMiddleware:
    """Gives every HTTP request an ID and writes one access log line for it.

    The ID is echoed in the `X-Request-ID` response header and set in
    `request_id_var` for the whole request, so every log line it causes carries it.
    Plain ASGI rather than BaseHTTPMiddleware, so it doesn't break contextvars or
    streamed responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        token = request_id_var.set(request_id)
        status: int | None = None
        start = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            # Starlette's ServerErrorMiddleware sits outside this one, so its 500
            # wouldn't carry the ID. Send the 500 here instead; it sees the
            # response as started and only re-raises.
            if status is None:
                await PlainTextResponse("Internal Server Error", status_code=500)(
                    scope, receive, send_with_id
                )
            self._log(scope, status, start, error=True)
            raise
        else:
            self._log(scope, status, start, error=False)
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _log(scope: Scope, status: int | None, start: float, *, error: bool) -> None:
        """The one access line for this request; ERROR with the traceback if it crashed."""
        access_logger.log(
            logging.ERROR if error else logging.INFO,
            "request",
            exc_info=error,
            extra={
                "method": scope["method"],
                "path": scope["path"],
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
            },
        )
