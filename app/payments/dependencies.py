"""Per-request overridable selection of the configured mock gateway."""

from typing import Annotated

from fastapi import Depends

from app.core.config import SettingsDep
from app.payments.gateway import MockPaymentGateway, PaymentGateway


def get_payment_gateway(settings: SettingsDep) -> PaymentGateway:
    # Settings rejects unsupported providers at startup. Keep explicit selection
    # here so adding a real provider requires a deliberate lifecycle change.
    if settings.payment_gateway != "mock":
        raise ValueError("Unsupported payment gateway configuration")
    return MockPaymentGateway()


PaymentGatewayDep = Annotated[PaymentGateway, Depends(get_payment_gateway)]
