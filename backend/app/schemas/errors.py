from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """One specific problem, such as a field that failed validation."""

    # The request field at fault, dotted for nested ones (`address.city`); None if
    # the problem isn't tied to one field.
    field: str | None
    # Machine-readable, e.g. `invalid_timezone` or `password_no_digit`.
    code: str
    message: str


class ErrorBody(BaseModel):
    # Machine-readable, e.g. `validation_error`, `email_taken`, `not_found`.
    code: str
    # For people; may change wording, so clients branch on `code`.
    message: str
    details: list[ErrorDetail]
    # The X-Request-ID of the failed request, for quoting in bug reports.
    request_id: str | None


class ErrorResponse(BaseModel):
    """The body of every 4xx and 5xx response."""

    error: ErrorBody
