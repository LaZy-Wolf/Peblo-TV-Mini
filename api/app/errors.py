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
