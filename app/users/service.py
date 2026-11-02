"""Account use cases; write operations commit once and reads never commit."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import InvalidCredentials
from app.security import dummy_password_hash, hash_password, verify_password
from app.users import repository
from app.users.errors import EmailInUse
from app.users.models import Role, User
from app.users.schemas import AccountCreateIn, normalize_email


def get_by_id(session: Session, user_id: int) -> User | None:
    return repository.get_by_id(session, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    return repository.get_by_email(session, email)


def _create_account(session: Session, account: AccountCreateIn, role: Role) -> User:
    user = User(
        email=account.email,
        full_name=account.full_name,
        password_hash=hash_password(account.password.get_secret_value()),
        role=role,
    )
    try:
        repository.add(session, user)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if (
            getattr(exc.orig, "sqlstate", None) == "23505"
            and exc.orig.diag.constraint_name == "uq_users_email_lower"
        ):
            raise EmailInUse() from None
        raise
    return user


def register_customer(session: Session, account: AccountCreateIn) -> User:
    return _create_account(session, account, Role.CUSTOMER)


def create_admin(session: Session, account: AccountCreateIn) -> User:
    """Local bootstrap use case only; never exposed through public registration."""
    return _create_account(session, account, Role.ADMIN)


def authenticate(session: Session, email: str, password: str) -> User:
    try:
        email = normalize_email(email)
    except ValueError:
        user = None
    else:
        user = repository.get_by_email(session, email)
    password_hash = dummy_password_hash() if user is None else user.password_hash
    valid_password = verify_password(password, password_hash)
    if user is None or not user.is_active or not valid_password:
        raise InvalidCredentials()
    return user
