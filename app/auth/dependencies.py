"""The single bearer-token entry point, followed by current database role checks."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.config import SettingsDep
from app.core.db import SessionDep
from app.errors import Forbidden, NotAuthenticated
from app.security import decode_access_token
from app.users import service as users
from app.users.identity import Principal
from app.users.roles import Role

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(_oauth2)], session: SessionDep, settings: SettingsDep
) -> Principal:
    if not token:
        raise NotAuthenticated()
    identity = decode_access_token(token, settings.jwt_secret.get_secret_value())
    user = users.get_by_id(session, identity.user_id)
    if user is None or not user.is_active or user.token_version != identity.token_version:
        raise NotAuthenticated()
    return user


CurrentUser = Annotated[Principal, Depends(get_current_user)]


def require_role(*roles: Role):
    def check_role(user: CurrentUser) -> Principal:
        if user.role not in roles:
            raise Forbidden()
        return user

    return Depends(check_role)
