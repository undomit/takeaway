"""Public customer registration and OAuth2 password-form login."""

from typing import Annotated

from fastapi import APIRouter, Form, Query, Response

from app.auth import service
from app.auth.schemas import LoginForm, NoQueryParameters, RegisterIn, TokenOut
from app.core.config import SettingsDep
from app.core.db import SessionDep
from app.users.schemas import AccountOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AccountOut, status_code=201)
def register(
    account: RegisterIn, session: SessionDep, _query: Annotated[NoQueryParameters, Query()]
) -> AccountOut:
    return AccountOut.from_user(service.register_customer(session, account))


@router.post("/token", response_model=TokenOut)
def login(
    form: Annotated[LoginForm, Form()],
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
    _query: Annotated[NoQueryParameters, Query()],
) -> TokenOut:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenOut(
        access_token=service.login(
            session, form.username, form.password.get_secret_value(), settings
        )
    )
