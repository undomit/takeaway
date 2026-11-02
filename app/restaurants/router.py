"""Admin restaurant onboarding and editing."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.auth.dependencies import require_role
from app.core.db import SessionDep
from app.core.schemas import NoQueryParameters, PositiveId
from app.restaurants import service
from app.restaurants.schemas import RestaurantCreateIn, RestaurantOut, RestaurantUpdateIn
from app.users.models import Role, User

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.post("", response_model=RestaurantOut, status_code=201)
def create_restaurant(
    data: RestaurantCreateIn,
    _admin: Annotated[User, require_role(Role.ADMIN)],
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> RestaurantOut:
    return RestaurantOut.model_validate(service.create_restaurant(session, data))


@router.patch("/{rid}", response_model=RestaurantOut)
def update_restaurant(
    rid: PositiveId,
    data: RestaurantUpdateIn,
    _admin: Annotated[User, require_role(Role.ADMIN)],
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> RestaurantOut:
    return RestaurantOut.model_validate(service.update_restaurant(session, rid, data))
