from typing import Annotated

import pytest
from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.errors import (
    BadRequest,
    Conflict,
    DomainError,
    Forbidden,
    InvalidCredentials,
    NotAuthenticated,
    NotFound,
    RuleViolation,
    TemporarilyUnavailable,
)


@pytest.mark.parametrize(
    ("error_type", "status"),
    [
        (BadRequest, 400),
        (NotAuthenticated, 401),
        (InvalidCredentials, 401),
        (Forbidden, 403),
        (NotFound, 404),
        (Conflict, 409),
        (RuleViolation, 422),
        (TemporarilyUnavailable, 503),
    ],
)
def test_domain_errors_use_central_http_mapping(application, error_type, status):
    @application.get("/test-error")
    def failing_use_case():
        raise error_type()

    with TestClient(application) as client:
        response = client.get("/test-error")
    assert response.status_code == status
    assert response.json() == {"detail": error_type.detail, "code": error_type.code}
    if status == 401:
        assert response.headers["WWW-Authenticate"] == "Bearer"
    else:
        assert "WWW-Authenticate" not in response.headers


def test_feature_error_subclass_retains_its_code_and_safe_detail(application):
    class StatusConflict(Conflict):
        code = "status_conflict"
        detail = "Order changed; refetch before trying again"

    @application.get("/test-error")
    def failing_use_case():
        raise StatusConflict()

    with TestClient(application) as client:
        response = client.get("/test-error")
    assert response.status_code == 409
    assert response.json() == {"code": StatusConflict.code, "detail": StatusConflict.detail}


def test_unclassified_domain_failure_does_not_expose_internal_details(application):
    @application.get("/test-error")
    def failing_use_case():
        raise DomainError("internal connection credentials")

    with TestClient(application) as client:
        response = client.get("/test-error")
    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "detail": "Internal server error"}


def test_request_validation_keeps_standard_fastapi_response(application):
    class Input(BaseModel):
        model_config = ConfigDict(extra="forbid")
        quantity: Annotated[int, Field(strict=True, ge=1, le=20)]

    @application.post("/test-validation")
    def validate_body(body: Annotated[Input, Body()]):
        return body

    with TestClient(application) as client:
        response = client.post("/test-validation", json={"quantity": 0, "unexpected": True})
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], list)
    assert {error["type"] for error in body["detail"]} == {"greater_than_equal", "extra_forbidden"}
