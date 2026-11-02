"""Three user-flow risks: test isolation, failed-request rollback and DB outage."""

import socket
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionDep, get_session
from app.errors import Conflict
from app.main import create_app
from tests.factories import create_probe, probe

pytestmark = pytest.mark.integration


def nested_read(session: SessionDep) -> Session:
    return session


def add_write_route(application):
    @application.post("/test-write")
    def write(
        session: SessionDep,
        nested_session: Annotated[Session, Depends(nested_read)],
        fail: bool = False,
    ):
        assert session is nested_session
        identifier = create_probe(session, "request write")
        if fail:
            raise Conflict()
        session.commit()
        return {"id": identifier}


def test_service_commits_are_visible_during_a_test_but_never_leak(
    rollback_sessions, database_client, database_engines
):
    runtime, _ = database_engines
    with rollback_sessions() as session, database_client(session) as client:
        application = client.app
        add_write_route(application)
        assert client.post("/test-write").status_code == 200
        assert client.post("/test-write").status_code == 200
        assert session.scalar(select(func.count()).select_from(probe)) == 2
    assert application.dependency_overrides == {}
    with rollback_sessions() as next_session:
        assert next_session.scalar(select(func.count()).select_from(probe)) == 0
    assert runtime.pool.checkedout() == 0


@pytest.mark.concurrency
def test_failed_request_rolls_back_and_releases_connections(
    committed_session_factory, database_client
):
    # This fixture deliberately uses real commits and privileged cleanup.
    with database_client() as client:
        application = client.app
        add_write_route(application)
        assert get_session not in application.dependency_overrides
        assert client.post("/test-write?fail=true").status_code == 409
        with committed_session_factory() as observer:
            assert observer.scalar(select(func.count()).select_from(probe)) == 0
        assert application.state.database.engine.pool.checkedout() == 0
        assert client.post("/test-write").status_code == 200
        with committed_session_factory() as observer:
            assert observer.scalar(select(func.count()).select_from(probe)) == 1
        assert application.state.database.engine.pool.checkedout() == 0


def test_database_outage_changes_readiness_but_not_liveness(settings, database_client):
    with database_client() as client:
        assert client.get("/readyz").json() == {"status": "ready"}
        assert client.get("/healthz").json() == {"status": "ok"}

    # Hold an unused local port without listening: deterministic connection refusal.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        broken_settings = settings.model_copy(
            update={
                "database_url": SecretStr(
                    f"postgresql+psycopg://private-user:private-password@127.0.0.1:{port}/unused"
                )
            }
        )
        with TestClient(create_app(broken_settings)) as client:
            response = client.get("/readyz")
            assert response.status_code == 503
            assert response.json() == {"status": "not_ready"}
            assert "private" not in response.text
            assert client.get("/healthz").status_code == 200
            assert client.app.state.database.engine.pool.checkedout() == 0
