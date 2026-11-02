"""Authenticated profile and credential management."""

from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.auth.dependencies import CurrentUser, require_role
from app.auth.schemas import NoQueryParameters
from app.core.db import SessionDep
from app.users import service
from app.users.models import Role, User
from app.users.schemas import AccountOut, ChangePasswordIn, ProfileUpdateIn

router = APIRouter(prefix="", tags=["users"])


@router.get("/me", response_model=AccountOut)
def read_profile(user: CurrentUser, _query: Annotated[NoQueryParameters, Query()]) -> AccountOut:
    return AccountOut.from_user(user)


@router.patch("/me", response_model=AccountOut)
def update_profile(
    profile: ProfileUpdateIn,
    user: Annotated[User, require_role(Role.CUSTOMER)],
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> AccountOut:
    return AccountOut.from_user(service.update_profile(session, user, profile))


@router.post("/me/log-out-everywhere", status_code=204)
def log_out_everywhere(
    user: CurrentUser, session: SessionDep, _query: Annotated[NoQueryParameters, Query()]
) -> Response:
    service.log_out_everywhere(session, user)
    return Response(status_code=204)


@router.post("/me/change-password", status_code=204)
def change_password(
    credentials: ChangePasswordIn,
    user: CurrentUser,
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> Response:
    service.change_password(session, user, credentials)
    return Response(status_code=204)
