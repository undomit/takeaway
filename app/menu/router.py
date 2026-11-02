"""Public menu browsing and restaurant-owned staff management."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.auth.dependencies import require_role
from app.core.db import SessionDep
from app.core.schemas import NoQueryParameters, PositiveId
from app.menu import service
from app.menu.schemas import (
    CategoryCreateIn,
    CategoryOut,
    CategoryUpdateIn,
    ItemCreateIn,
    ItemOut,
    ItemUpdateIn,
    MenuOut,
)
from app.users.models import Role, User

router = APIRouter(prefix="/restaurants", tags=["menu"])
Staff = Annotated[User, require_role(Role.STAFF)]
EmptyQuery = Annotated[NoQueryParameters, Query()]


@router.get("/{rid}/menu", response_model=MenuOut)
def read_menu(rid: PositiveId, session: SessionDep, _query: EmptyQuery) -> MenuOut:
    return service.read_menu(session, rid)


@router.post("/{rid}/menu/categories", response_model=CategoryOut, status_code=201)
def create_category(
    rid: PositiveId, data: CategoryCreateIn, staff: Staff, session: SessionDep, _query: EmptyQuery
) -> CategoryOut:
    return CategoryOut.model_validate(
        service.create_category(session, rid, staff.restaurant_id, data)
    )


@router.patch("/{rid}/menu/categories/{cid}", response_model=CategoryOut)
def update_category(
    rid: PositiveId,
    cid: PositiveId,
    data: CategoryUpdateIn,
    staff: Staff,
    session: SessionDep,
    _query: EmptyQuery,
) -> CategoryOut:
    return CategoryOut.model_validate(
        service.update_category(session, rid, cid, staff.restaurant_id, data)
    )


@router.post("/{rid}/menu/items", response_model=ItemOut, status_code=201)
def create_item(
    rid: PositiveId, data: ItemCreateIn, staff: Staff, session: SessionDep, _query: EmptyQuery
) -> ItemOut:
    return ItemOut.model_validate(service.create_item(session, rid, staff.restaurant_id, data))


@router.patch("/{rid}/menu/items/{mid}", response_model=ItemOut)
def update_item(
    rid: PositiveId,
    mid: PositiveId,
    data: ItemUpdateIn,
    staff: Staff,
    session: SessionDep,
    _query: EmptyQuery,
) -> ItemOut:
    return ItemOut.model_validate(service.update_item(session, rid, mid, staff.restaurant_id, data))


@router.post("/{rid}/menu/items/{mid}/archive", response_model=ItemOut)
def archive_item(
    rid: PositiveId, mid: PositiveId, staff: Staff, session: SessionDep, _query: EmptyQuery
) -> ItemOut:
    return ItemOut.model_validate(service.archive_item(session, rid, mid, staff.restaurant_id))
