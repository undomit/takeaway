"""Account use cases; write operations commit once and reads never commit."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import Forbidden, InvalidCredentials, NotAuthenticated, NotFound
from app.restaurants import service as restaurants
from app.security import dummy_password_hash, hash_password, verify_password
from app.users import repository
from app.users.errors import EmailInUse
from app.users.models import Role, User
from app.users.schemas import (
    AccountCreateIn,
    ChangePasswordIn,
    ProfileUpdateIn,
    StaffCreateIn,
    normalize_email,
)


def get_by_id(session: Session, user_id: int) -> User | None:
    return repository.get_by_id(session, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    return repository.get_by_email(session, email)


def _create_account(
    session: Session, account: AccountCreateIn, role: Role, restaurant_id: int | None = None
) -> User:
    user = User(
        email=account.email,
        full_name=account.full_name,
        password_hash=hash_password(account.password.get_secret_value()),
        role=role,
        restaurant_id=restaurant_id,
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
    except Exception:
        session.rollback()
        raise
    return user


def register_customer(session: Session, account: AccountCreateIn) -> User:
    return _create_account(session, account, Role.CUSTOMER)


def create_admin(session: Session, account: AccountCreateIn) -> User:
    """Local bootstrap use case only; never exposed through public registration."""
    return _create_account(session, account, Role.ADMIN)


def create_staff(session: Session, account: StaffCreateIn) -> User:
    restaurants.get_by_id(session, account.restaurant_id)
    return _create_account(session, account, Role.STAFF, restaurant_id=account.restaurant_id)


def deactivate_user(session: Session, user_id: int) -> User:
    try:
        user = repository.get_for_update(session, user_id)
        if user is None:
            raise NotFound()
        if user.is_active:
            user.is_active = False
            user.token_version += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return user


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


def _lock_authenticated(session: Session, current_user: User) -> User:
    # Capture the authenticated version before populate_existing refreshes the
    # same ORM instance. Recheck under lock if revocation raced authentication.
    token_version = current_user.token_version
    user = repository.get_for_update(session, current_user.id)
    if user is None or not user.is_active or user.token_version != token_version:
        raise NotAuthenticated()
    return user


def update_profile(session: Session, current_user: User, profile: ProfileUpdateIn) -> User:
    try:
        user = _lock_authenticated(session, current_user)
        if user.role != Role.CUSTOMER:
            raise Forbidden()
        if "full_name" in profile.model_fields_set:
            user.full_name = profile.full_name
        if "saved_address" in profile.model_fields_set:
            address = profile.saved_address
            user.address_line1 = address.address_line1 if address else None
            user.address_line2 = address.address_line2 if address else None
            user.postcode = address.postcode if address else None
            user.phone = address.phone if address else None
        session.commit()
    except Exception:
        session.rollback()
        raise
    return user


def log_out_everywhere(session: Session, current_user: User) -> None:
    try:
        user = _lock_authenticated(session, current_user)
        user.token_version += 1
        session.commit()
    except Exception:
        session.rollback()
        raise


def change_password(session: Session, current_user: User, credentials: ChangePasswordIn) -> None:
    try:
        user = _lock_authenticated(session, current_user)
        if not verify_password(credentials.current_password.get_secret_value(), user.password_hash):
            raise InvalidCredentials()
        user.password_hash = hash_password(credentials.new_password.get_secret_value())
        user.token_version += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
