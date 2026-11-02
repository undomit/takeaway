"""Order HTTP dependencies, ready for the atomic placement endpoint in task 016."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.exceptions import RequestValidationError

from app.orders.idempotency import parse_idempotency_key


def get_idempotency_key(
    values: Annotated[list[str] | None, Header(alias="Idempotency-Key")] = None,
) -> UUID:
    try:
        return parse_idempotency_key(values)
    except ValueError as exc:
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("header", "Idempotency-Key"), "msg": str(exc)}]
        ) from None


IdempotencyKey = Annotated[UUID, Depends(get_idempotency_key)]
