"""Translate domain failures and preserve safe FastAPI validation responses."""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
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


async def safe_validation_error_handler(request: Request, exc: RequestValidationError):
    # Keep FastAPI's detail-list response, without reflecting request passwords or
    # whole submitted objects in the optional input metadata.
    errors = [
        {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
    ]
    return await request_validation_exception_handler(request, RequestValidationError(errors))


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # ServerErrorMiddleware runs outside installed request middleware. Preserve
    # correlation on its response without disclosing exception/SQL details.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "internal_error"},
        headers={"X-Request-ID": request.state.request_id},
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(RequestValidationError, safe_validation_error_handler)
