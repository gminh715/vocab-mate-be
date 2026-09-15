"""Custom exceptions and centralized exception handlers for standard JSON envelopes."""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

HTTP_STATUS_TO_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422): "UNPROCESSABLE_ENTITY",
    status.HTTP_429_TOO_MANY_REQUESTS: "TOO_MANY_REQUESTS",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
}


class AppException(HTTPException):
    """Application-specific HTTP exception with structured error envelope metadata.

    Attributes:
        status_code (int): HTTP response status code.
        code (str): Machine-readable upper-snake error code identifier.
        message (str): Human-readable error message.
        details (list[str] | None): Optional list of supplementary detail strings.
        issues (list[dict] | None): Optional structured field issues.

    Example:
        >>> exc = AppException(status_code=400, code="INVALID_INPUT", message="Bad value")
        >>> exc.code
        'INVALID_INPUT'
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[str] | None = None,
        issues: list[dict] | None = None,
    ):
        """Initializes application exception.

        Args:
            status_code (int): HTTP status code.
            code (str): Error category code.
            message (str): Explanatory message.
            details (list[str] | None, optional): Granular messages. Defaults to None.
            issues (list[dict] | None, optional): Structured issue payloads. Defaults to None.
        """
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details
        self.issues = issues


def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Formats an AppException into the standard JSON error envelope.

    Args:
        request (Request): The incoming HTTP request.
        exc (AppException): The raised application exception.

    Returns:
        JSONResponse: Standard error envelope response.

    Example:
        >>> from unittest.mock import MagicMock
        >>> req = MagicMock(spec=Request)
        >>> ex = AppException(400, "BAD_DATA", "Data is invalid")
        >>> resp = app_exception_handler(req, ex)
        >>> resp.status_code
        400
    """
    content: dict[str, Any] = {
        "success": False,
        "error": {
            "code": exc.code,
            "message": exc.message,
        },
    }
    if exc.details:
        content["error"]["details"] = exc.details
    if exc.issues:
        content["error"]["issues"] = exc.issues
    return JSONResponse(status_code=exc.status_code, content=content)


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Standardizes any raised HTTPException into the unified error envelope.

    Args:
        request (Request): The incoming HTTP request.
        exc (HTTPException): The raised HTTP exception.

    Returns:
        JSONResponse: Standardized JSON envelope response matching frontend contract.

    Example:
        >>> from unittest.mock import MagicMock
        >>> req = MagicMock(spec=Request)
        >>> ex = HTTPException(status_code=404, detail="Not Found")
        >>> resp = http_exception_handler(req, ex)
        >>> resp.status_code
        404
    """
    code = HTTP_STATUS_TO_CODE.get(exc.status_code, "ERROR")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    content: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    return JSONResponse(status_code=exc.status_code, content=content)


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Formats validation errors into the standard error envelope.

    Args:
        request (Request): The incoming HTTP request.
        exc (RequestValidationError): Pydantic request validation error.

    Returns:
        JSONResponse: Standardized validation error response.

    Example:
        >>> from unittest.mock import MagicMock
        >>> req = MagicMock(spec=Request)
        >>> err = RequestValidationError([{"loc": ("body", "email"), "msg": "invalid"}])
        >>> resp = validation_exception_handler(req, err)
        >>> resp.status_code
        400
    """
    details = [f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "BAD_REQUEST",
                "message": "Validation failed",
                "details": details,
            },
        },
    )


import logging

logger = logging.getLogger("vocab_mate.exceptions")


def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled exceptions and returns a generic 500 JSON envelope.

    Args:
        request (Request): The incoming HTTP request.
        exc (Exception): The unhandled exception.

    Returns:
        JSONResponse: 500 Internal Server Error envelope response.

    Example:
        >>> from unittest.mock import MagicMock
        >>> req = MagicMock(spec=Request)
        >>> resp = generic_exception_handler(req, RuntimeError("crash"))
        >>> resp.status_code
        500
    """
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Internal server error",
            },
        },
    )
