"""Synchronous persistence infrastructure; write services own their commit."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_size=10,
            max_overflow=5,
            pool_timeout=5,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def is_available(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    def dispose(self) -> None:
        self.engine.dispose()


def get_database(request: Request) -> Database:
    return request.app.state.database


DatabaseDep = Annotated[Database, Depends(get_database)]


def get_session(database: DatabaseDep) -> Iterator[Session]:
    # FastAPI caches this dependency, so nested services/dependencies share one session.
    with database.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        # Session.close() also rolls back any uncommitted work on a successful request.


SessionDep = Annotated[Session, Depends(get_session)]
