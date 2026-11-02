"""Submitted order intent and distinct immutable-receipt/current-detail responses."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    UUID4,
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictBool,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.address import AddressIn
from app.core.schemas import JsonId
from app.orders.pricing import PricedLine, PricedOrder
from app.orders.status import Status
from app.orders.values import Selections
from app.users.roles import Role

Notes = Annotated[str, StringConstraints(strict=True, max_length=2000)]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(UTC)


UtcTimestamp = Annotated[
    datetime,
    AfterValidator(_utc),
    PlainSerializer(
        lambda value: value.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        return_type=str,
        when_used="json",
    ),
]


class OrderCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    restaurant_id: JsonId
    lines: Selections
    delivery_address: AddressIn | None = None
    notes: Notes | None = None


class AddressSnapshot(AddressIn):
    model_config = ConfigDict(frozen=True)


class OrderLineOut(PricedLine):
    model_config = ConfigDict(from_attributes=True)
    id: JsonId


class OrderSnapshot(PricedOrder):
    """Only persisted immutable values shared by creation and current reads."""

    id: UUID4
    restaurant_id: JsonId
    paid: StrictBool
    delivery_address: AddressSnapshot
    notes: Notes | None
    lines: Annotated[tuple[OrderLineOut, ...], Field(min_length=1, max_length=100)]
    created_at: UtcTimestamp

    @field_validator("lines")
    @classmethod
    def order_lines(cls, lines: tuple[OrderLineOut, ...]) -> tuple[OrderLineOut, ...]:
        if len({line.id for line in lines}) != len(lines) or len(
            {line.menu_item_id for line in lines}
        ) != len(lines):
            raise ValueError("Persisted line IDs and menu item IDs must be unique")
        return tuple(sorted(lines, key=lambda line: line.id))


class CreationReceipt(OrderSnapshot):
    status: Literal[Status.PENDING] = Status.PENDING
    paid: Literal[True] = True


class StatusChangeOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)
    id: JsonId
    from_status: Status | None
    to_status: Status
    actor_user_id: JsonId
    actor_role: Role
    reason: (
        Annotated[str, StringConstraints(strict=True, strip_whitespace=True, max_length=1000)]
        | None
    )
    created_at: UtcTimestamp

    @model_validator(mode="after")
    def validate_initial(self) -> "StatusChangeOut":
        if self.from_status is None and (
            self.to_status != Status.PENDING
            or self.actor_role != Role.CUSTOMER
            or self.reason is not None
        ):
            raise ValueError(
                "Initial history must record customer placement as pending without reason"
            )
        return self


class OrderDetail(OrderSnapshot):
    status: Status
    customer_id: JsonId
    updated_at: UtcTimestamp
    status_changes: Annotated[tuple[StatusChangeOut, ...], Field(min_length=1)]

    @field_validator("status_changes")
    @classmethod
    def order_history(cls, history: tuple[StatusChangeOut, ...]) -> tuple[StatusChangeOut, ...]:
        if len({change.id for change in history}) != len(history):
            raise ValueError("Status change IDs must be unique")
        return tuple(sorted(history, key=lambda change: (change.created_at, change.id)))

    @computed_field
    @property
    def refund_owed(self) -> bool:
        return self.paid and self.status in {Status.REJECTED, Status.CANCELLED}


def creation_receipt(snapshot: OrderSnapshot, initial_change: StatusChangeOut) -> CreationReceipt:
    """Rebuild stable creation output from snapshots and the initial event only.

    A current detail can be supplied: current status/refund/history/updated_at are
    deliberately excluded. No profile/menu lookup or mutable response cache is used.
    """
    if initial_change.from_status is not None or initial_change.to_status != Status.PENDING:
        raise ValueError("Creation receipt requires the initial placement status change")
    fields = {name: getattr(snapshot, name) for name in OrderSnapshot.model_fields}
    return CreationReceipt(**fields, status=initial_change.to_status)
