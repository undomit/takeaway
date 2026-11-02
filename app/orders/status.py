"""The seven order statuses and their terminal/active partitions."""

from enum import StrEnum


class Status(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset({Status.DELIVERED, Status.REJECTED, Status.CANCELLED})
ACTIVE_STATUSES = frozenset(Status) - TERMINAL_STATUSES
