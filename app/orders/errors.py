"""Order-domain failures; transport mapping is centralized."""

from app.errors import BadRequest, Conflict, Forbidden, RuleViolation


class InvalidTransition(Conflict):
    code = "invalid_transition"
    detail = "This order status change is not allowed"


class TransitionNotPermitted(Forbidden):
    code = "transition_not_permitted"
    detail = "Your role cannot make this order status change"


class ReasonRequired(RuleViolation):
    code = "reason_required"
    detail = "A reason is required for this order status change"


class IdempotencyKeyRequired(BadRequest):
    code = "idempotency_key_required"
    detail = "Idempotency-Key header is required"
