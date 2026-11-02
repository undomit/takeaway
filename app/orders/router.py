"""Atomic checkout and scoped order history/detail/polling."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from fastapi.exceptions import RequestValidationError

from app.auth.dependencies import CurrentUser, require_role
from app.core.config import SettingsDep
from app.core.db import SessionDep
from app.core.schemas import NoQueryParameters
from app.orders import service
from app.orders.dependencies import IdempotencyKey
from app.orders.errors import InvalidOrderPricing
from app.orders.schemas import (
    ActiveOrders,
    CreationReceipt,
    OrderCreateIn,
    OrderDetail,
    OrderListQuery,
    OrderPage,
    StatusChangeIn,
)
from app.payments.dependencies import PaymentGatewayDep
from app.users.models import User
from app.users.roles import Role

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=CreationReceipt, status_code=201)
def place_order(
    request: OrderCreateIn,
    customer: Annotated[User, require_role(Role.CUSTOMER)],
    key: IdempotencyKey,
    session: SessionDep,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
    response: Response,
    _query: Annotated[NoQueryParameters, Query()],
) -> CreationReceipt:
    try:
        placed = service.place_order(
            session, customer.id, key, request, settings.platform_currency, gateway
        )
    except InvalidOrderPricing as exc:
        raise RequestValidationError(
            [{**error, "loc": ("body", *error["loc"])} for error in exc.errors]
        ) from None
    if placed.replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return placed.receipt


@router.get("", response_model=OrderPage | ActiveOrders)
def list_orders(
    query: Annotated[OrderListQuery, Query()], user: CurrentUser, session: SessionDep
) -> OrderPage | ActiveOrders:
    return service.list_orders(session, user, query)


@router.get("/{oid}", response_model=OrderDetail)
def read_order(
    oid: UUID,
    user: CurrentUser,
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> OrderDetail:
    return service.get_order(session, user, oid)


@router.post("/{oid}/status-changes", response_model=OrderDetail)
def change_status(
    oid: UUID,
    request: StatusChangeIn,
    actor: Annotated[User, require_role(Role.CUSTOMER, Role.STAFF)],
    session: SessionDep,
    _query: Annotated[NoQueryParameters, Query()],
) -> OrderDetail:
    return service.change_status(session, actor, oid, request)
