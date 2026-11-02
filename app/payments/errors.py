"""Safe domain outcomes translated to HTTP by the common handler."""

from app.errors import Conflict, TemporarilyUnavailable


class PaymentDeclined(Conflict):
    code = "payment_declined"
    detail = "Payment was declined"


class PaymentUnavailable(TemporarilyUnavailable):
    code = "payment_unavailable"
    detail = "Payment is temporarily unavailable"
