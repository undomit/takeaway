"""Auth use cases access account persistence through users.service only."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.auth.schemas import RegisterIn
from app.core.config import Settings
from app.security import create_access_token
from app.users import service as users
from app.users.models import Role, User


def register_customer(session: Session, account: RegisterIn) -> User:
    return users.register_customer(session, account)


def login(session: Session, username: str, password: str, settings: Settings) -> str:
    user = users.authenticate(session, username, password)
    lifetime = timedelta(days=30) if user.role == Role.CUSTOMER else timedelta(hours=12)
    return create_access_token(
        user.id, user.token_version, lifetime, settings.jwt_secret.get_secret_value()
    )
