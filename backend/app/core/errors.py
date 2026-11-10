"""The one error body every 4xx and 5xx response uses: see `ErrorResponse`."""

from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var
from app.schemas.errors import ErrorBody, ErrorDetail, ErrorResponse


class AppError(Exception):
    """A failure the API reports to the caller. Subclasses set the status and code."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be processed"
    # Extra response headers, e.g. WWW-Authenticate on a 401.
    headers: Mapping[str, str] | None = None

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries documenting `ErrorResponse` for these status codes.

    Routes with a body or parameters must list 422 here: otherwise FastAPI documents
    its own validation-error schema, which this app never sends.
    """
    return {
        code: {"model": ErrorResponse, "description": HTTPStatus(code).phrase}
        for code in status_codes
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Sequence[ErrorDetail] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """An `ErrorResponse` JSON response, carrying the current request's ID."""
    body = ErrorResponse(
        error=ErrorBody(
            code=code, message=message, details=list(details), request_id=request_id_var.get()
        )
    )
    return JSONResponse(body.model_dump(mode="json"), status_code=status_code, headers=headers)


def _code_for(status_code: int) -> str:
    """`not_found` for 404 and so on: the standard reason phrase in snake case."""
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return "error"
    return phrase.lower().replace(" ", "_").replace("-", "_")


def _field(loc: Sequence[int | str]) -> str | None:
    """`timezone` for `("body", "timezone")`, `query.limit` for a query parameter, and
    None for the body as a whole."""
    parts = [str(part) for part in loc]
    if parts and parts[0] == "body":
        parts = parts[1:]
    return ".".join(parts) or None


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Built field by field: Pydantic's own errors carry the submitted `input`, which
    # may be a password, so they're never passed through.
    errors: Sequence[Mapping[str, Any]] = exc.errors()
    details = [
        ErrorDetail(field=_field(error["loc"]), code=error["type"], message=error["msg"])
        for error in errors
    ]
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", "The request is invalid", details
    )


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return error_response(
        exc.status_code, _code_for(exc.status_code), str(exc.detail), headers=exc.headers
    )


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message, headers=exc.headers)


def internal_error_response() -> JSONResponse:
    """The 500 for an unhandled exception. It says nothing about the cause."""
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Internal server error"
    )


def install_error_handlers(app: FastAPI) -> None:
    """Send every handled error through `error_response`.

    Unhandled exceptions become a 500 in RequestContextMiddleware, which sits inside
    Starlette's ServerErrorMiddleware and so answers first.
    """
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(AppError, _app_error)
