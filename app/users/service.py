"""Read-only account lookups used across feature boundaries, including auth."""

from sqlalchemy.orm import Session

from app.users import repository
from app.users.models import User


def get_by_id(session: Session, user_id: int) -> User | None:
    return repository.get_by_id(session, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    return repository.get_by_email(session, email)
