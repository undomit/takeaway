"""Mock-only synchronous payment seam, independent of HTTP and persistence."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class PaymentOutcome(StrEnum):
    PAID = "paid"
    DECLINED = "declined"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PaymentResult:
    outcome: PaymentOutcome


class PaymentGateway(Protocol):
    def create_payment(
        self, order_id: UUID, amount_minor: int, currency: str, idempotency_key: UUID
    ) -> PaymentResult:
        """Return a payment outcome; the caller owns rollback/commit policy."""
        ...


class MockPaymentGateway:
    def create_payment(
        self, order_id: UUID, amount_minor: int, currency: str, idempotency_key: UUID
    ) -> PaymentResult:
        return PaymentResult(PaymentOutcome.PAID)
