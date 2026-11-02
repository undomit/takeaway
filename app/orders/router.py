"""Customer-only atomic order placement; read/status routes arrive later."""

from typing import Annotated

from fastapi import APIRouter, Query, Response
from fastapi.exceptions import RequestValidationError

from app.auth.dependencies import require_role
from app.core.config import SettingsDep
from app.core.db import SessionDep
from app.core.schemas import NoQueryParameters
from app.orders import service
from app.orders.dependencies import IdempotencyKey
from app.orders.errors import InvalidOrderPricing
from app.orders.schemas import CreationReceipt, OrderCreateIn
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
