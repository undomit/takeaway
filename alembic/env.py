"""Migrations use owner credentials, never the application's runtime account."""

from sqlalchemy import create_engine, pool

from alembic import context
from app import models  # noqa: F401 - registers all feature metadata
from app.core.config import MigrationSettings
from app.core.db import Base

target_metadata = Base.metadata


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=MigrationSettings().migration_database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
    else:
        engine = create_engine(
            MigrationSettings().migration_database_url.get_secret_value(),
            poolclass=pool.NullPool,
            connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
        )
        try:
            with engine.connect() as connection:
                run_migrations(connection)
        finally:
            engine.dispose()
