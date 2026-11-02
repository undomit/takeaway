"""Translate domain failures without replacing FastAPI validation handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import (
    BadRequest,
    Conflict,
    DomainError,
    Forbidden,
    NotAuthenticated,
    NotFound,
    RuleViolation,
    TemporarilyUnavailable,
)

_ERROR_STATUSES = {
    BadRequest: 400,
    NotAuthenticated: 401,
    Forbidden: 403,
    NotFound: 404,
    Conflict: 409,
    RuleViolation: 422,
    TemporarilyUnavailable: 503,
}


def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    for error_type in type(exc).__mro__:
        if error_type in _ERROR_STATUSES:
            status_code = _ERROR_STATUSES[error_type]
            break
    else:
        # An unclassified internal failure must not expose arbitrary exception details.
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else None,
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(DomainError, domain_error_handler)
