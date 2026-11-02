"""Account queries; callers own the transaction and account policies."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.users.models import User


def get_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    # Use the same PostgreSQL lower() expression as the uniqueness index.
    return session.scalar(select(User).where(func.lower(User.email) == func.lower(email.strip())))


def get_for_update(session: Session, user_id: int) -> User | None:
    # Authentication may already have loaded this identity. Refresh it after
    # acquiring the lock so a concurrent credential change cannot be overwritten.
    return session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def add(session: Session, user: User) -> User:
    session.add(user)
    session.flush()
    return user
