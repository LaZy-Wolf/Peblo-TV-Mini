from dataclasses import asdict, dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class ApiError:
    code: str
    message: str
    field: str | None = None


class ApiException(Exception):
    def __init__(self, status_code: int, errors: list[ApiError]):
        self.status_code = status_code
        self.errors = errors
        super().__init__(errors[0].message if errors else "error")


def error_response(status_code: int, errors: list[ApiError]) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"errors": [asdict(e) for e in errors]},
    )


async def api_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiException)
    return error_response(exc.status_code, exc.errors)


_FRIENDLY = {
    "missing": "This is required.",
    "int_parsing": "This needs to be a whole number.",
    "greater_than_equal": "This number is too small.",
    "string_too_short": "This is too short.",
}


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Map FastAPI's own request validation errors into the same envelope.

    Without this, a bad request body returns FastAPI's `detail` shape while
    every other error returns `errors`, and the CMS would need two code paths
    to show one message.
    """
    errors = []
    for problem in getattr(exc, "errors", lambda: [])():
        location = [str(part) for part in problem["loc"] if part != "body"]
        field = ".".join(location) or None
        message = _FRIENDLY.get(problem["type"])
        if message is None:
            message = problem["msg"][:1].upper() + problem["msg"][1:]
            if not message.endswith("."):
                message += "."
        errors.append(ApiError(f"invalid_{problem['type']}", message, field))
    if not errors:
        errors = [ApiError("invalid_request", "We could not read that request.")]
    return error_response(422, errors)
