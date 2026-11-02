"""Dedicated PostgreSQL test configuration and privileged cleanup."""

from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import inspect
from sqlalchemy.engine import Engine, make_url

from app.core.config import validate_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEST_",
        env_file=PROJECT_ROOT / ".env.test",
        extra="ignore",
        hide_input_in_errors=True,
    )
    database_url: SecretStr
    migration_database_url: SecretStr
    _validate_urls = field_validator("database_url", "migration_database_url")(
        validate_database_url
    )

    @model_validator(mode="after")
    def require_disposable_database(self):
        runtime = make_url(self.database_url.get_secret_value())
        owner = make_url(self.migration_database_url.get_secret_value())
        if (
            runtime.database != "takeaway_test"
            or (runtime.host, runtime.port, runtime.database)
            != (owner.host, owner.port, owner.database)
            or runtime.username == owner.username
        ):
            raise ValueError("Tests require takeaway_test with distinct runtime and owner accounts")
        return self


def clean_committed_data(owner_engine: Engine) -> None:
    """Only called against the explicitly validated, exclusively used test database."""
    quote = owner_engine.dialect.identifier_preparer.quote
    with owner_engine.begin() as connection:
        inspector = inspect(connection)
        tables = [
            f"{quote(schema)}.{quote(name)}"
            for schema in ("public", "test_support")
            for name in inspector.get_table_names(schema=schema)
            if not (schema == "public" and name == "alembic_version")
        ]
        if tables:
            connection.exec_driver_sql(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
