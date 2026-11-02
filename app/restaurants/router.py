"""Admin restaurant onboarding and editing."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.auth.dependencies import require_role
from app.core.db import SessionDep
from app.core.schemas import NoQueryParameters, PositiveId
from app.restaurants import service
from app.restaurants.schemas import (
    AcceptingOrdersIn,
    RestaurantCreateIn,
    RestaurantListQuery,
    RestaurantOut,
    RestaurantPage,
    RestaurantUpdateIn,
)
from app.users.models import Role, User

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=RestaurantPage)
def list_restaurants(
    query: Annotated[RestaurantListQuery, Query()], session: SessionDep
) -> RestaurantPage:
    return service.list_restaurants(session, query)


@router.get("/{rid}", response_model=RestaurantOut)
def read_restaurant(
    rid: PositiveId, session: SessionDep, _query: Annotated[NoQueryParameters, Query()]
) -> RestaurantOut:
    return RestaurantOut.model_validate(service.get_by_id(session, rid))


@router.patch("/{rid}/accepting-orders", response_model=RestaurantOut)
def set_accepting_orders(
    rid: PositiveId,
    data: AcceptingOrdersIn,
    staff: Annotated[User, require_role(Role.STAFF)],
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> RestaurantOut:
    return RestaurantOut.model_validate(
        service.set_accepting_orders(session, rid, staff.restaurant_id, data.is_accepting_orders)
    )


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
