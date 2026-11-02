"""Tests are independent of local secrets, dotenv files and the settings cache."""

import pytest

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in (
        "JWT_SECRET",
        "PLATFORM_CURRENCY",
        "DATABASE_URL",
        "jwt_secret",
        "platform_currency",
        "database_url",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused:unused@127.0.0.1:1/unused",
        jwt_secret="test-only-secret-that-is-not-for-production",
        platform_currency="EUR",
    )


@pytest.fixture
def application(settings):
    return create_app(settings)


@pytest.fixture(scope="session")
def database_engines():
    """Migrate once with the owner; all request/session work uses the runtime role."""
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    from alembic import command
    from app.core.db import Database
    from tests.database import PROJECT_ROOT, TestDatabaseSettings
    from tests.factories import probe

    urls = TestDatabaseSettings()
    runtime = Database(
        Settings(
            _env_file=None,
            database_url=urls.database_url,
            jwt_secret="test-only-secret-that-is-not-for-production",
            platform_currency="EUR",
        )
    )
    owner = create_engine(
        urls.migration_database_url.get_secret_value(),
        poolclass=NullPool,
        connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
    )
    support_created = False
    try:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        with owner.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
            connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS test_support")
            probe.create(connection, checkfirst=True)
            role = connection.dialect.identifier_preparer.quote(runtime.engine.url.username)
            connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA test_support TO {role}")
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON test_support.request_probe TO {role}"
            )
            connection.exec_driver_sql(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA test_support TO {role}"
            )
        support_created = True
        with runtime.engine.connect() as connection:
            assert not connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            ), "Test requests must not use a PostgreSQL superuser"
            assert not connection.scalar(
                text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            ), "Test requests must not own/create the application schema"
        yield runtime.engine, owner
    finally:
        try:
            if support_created:
                with owner.begin() as connection:
                    connection.exec_driver_sql("DROP SCHEMA IF EXISTS test_support CASCADE")
        finally:
            runtime.dispose()
            owner.dispose()


@pytest.fixture
def rollback_sessions(database_engines):
    from contextlib import contextmanager

    from sqlalchemy.orm import Session

    runtime, _ = database_engines

    @contextmanager
    def isolated_session():
        with runtime.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    yield session
            finally:
                transaction.rollback()

    return isolated_session


@pytest.fixture
def db_session(rollback_sessions):
    with rollback_sessions() as session:
        yield session


@pytest.fixture
def database_client(settings, database_engines):
    from contextlib import contextmanager

    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    from app.core.db import get_session

    runtime, _ = database_engines

    @contextmanager
    def client_context(session=None):
        config = settings.model_copy(
            update={"database_url": SecretStr(runtime.url.render_as_string(hide_password=False))}
        )
        application = create_app(config)
        if session is not None:
            application.dependency_overrides[get_session] = lambda: session
        try:
            with TestClient(application) as client:
                yield client
        finally:
            application.dependency_overrides.clear()

    return client_context


@pytest.fixture
def client(db_session, database_client):
    with database_client(db_session) as test_client:
        yield test_client


@pytest.fixture
def committed_session_factory(request, database_engines):
    """Real commits for production-lifecycle/concurrency tests; never the rollback fixture."""
    from sqlalchemy.orm import sessionmaker

    from tests.database import clean_committed_data

    if "db_session" in request.fixturenames or "client" in request.fixturenames:
        pytest.fail("Committed-data tests cannot also use the rollback fixtures")
    runtime, owner = database_engines
    clean_committed_data(owner)
    try:
        yield sessionmaker(bind=runtime, expire_on_commit=False)
    finally:
        clean_committed_data(owner)
