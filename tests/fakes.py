"""Small payment doubles; authentication and persistence stay real in integration tests."""

from uuid import UUID

from app.payments.gateway import PaymentOutcome, PaymentResult


class RecordingPaymentGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int, str, UUID]] = []

    def create_payment(
        self, order_id: UUID, amount_minor: int, currency: str, idempotency_key: UUID
    ) -> PaymentResult:
        self.calls.append((order_id, amount_minor, currency, idempotency_key))
        return PaymentResult(PaymentOutcome.PAID)
