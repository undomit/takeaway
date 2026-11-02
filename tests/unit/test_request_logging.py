"""Request correlation and access records stay useful without retaining private input."""

import io
import json
import logging

from fastapi.testclient import TestClient

from app.core.request_logging import logger


def test_request_ids_and_safe_json_records_cover_success_validation_and_unknown_routes(
    application, monkeypatch
):
    output = io.StringIO()
    monkeypatch.setattr(logger, "handlers", [logging.StreamHandler(output)])

    @application.post("/test-log/{item_id}")
    def probe(item_id: int):
        return {"id": item_id}

    with TestClient(application) as client:
        response = client.post(
            "/test-log/42?token=query-secret",
            headers={
                "X-Request-ID": "proxy-request_123",
                "Authorization": "Bearer private-token",
            },
            json={"password": "private-password", "phone": "private-phone"},
        )
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "proxy-request_123"
        invalid = client.post("/test-log/not-an-integer", headers={"X-Request-ID": "bad id"})
        assert invalid.status_code == 422
        assert len(invalid.headers["X-Request-ID"]) == 32
        unknown = client.get(
            "/private-address-in-path",
            headers=[
                ("X-Request-ID", "one"),
                ("X-Request-ID", "two"),
            ],
        )
        assert unknown.status_code == 404 and len(unknown.headers["X-Request-ID"]) == 32
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(rows) == 3
    assert [row["status"] for row in rows] == [200, 422, 404]
    assert [row["route"] for row in rows] == [
        "/test-log/{item_id}",
        "/test-log/{item_id}",
        "unmatched",
    ]
    assert [row["request_id"] for row in rows] == [
        response.headers["X-Request-ID"],
        invalid.headers["X-Request-ID"],
        unknown.headers["X-Request-ID"],
    ]
    for row in rows:
        assert row["event"] == "request" and row["duration_ms"] >= 0
        assert row["timestamp"].endswith("Z")
    for private in (
        "query-secret",
        "private-token",
        "private-password",
        "private-phone",
        "private-address-in-path",
        "bad id",
    ):
        assert private not in output.getvalue()


def test_unexpected_errors_keep_correlation_without_exception_details(application, monkeypatch):
    from app.core.request_logging import SafeServerFormatter

    output = io.StringIO()
    monkeypatch.setattr(logger, "handlers", [logging.StreamHandler(output)])

    @application.get("/test-unexpected")
    def failure():
        raise RuntimeError("private SQL/address/password")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/test-unexpected", headers={"X-Request-ID": "failed-request"})
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "failed-request"
    record = json.loads(output.getvalue())
    assert record["status"] == 500 and record["request_id"] == "failed-request"
    assert "private" not in output.getvalue() + response.text
    server_record = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        __file__,
        1,
        "private SQL/address/password",
        (),
        (RuntimeError, RuntimeError("private"), None),
    )
    assert (
        json.loads(SafeServerFormatter().format(server_record))["message"]
        == "Unhandled application error"
    )
