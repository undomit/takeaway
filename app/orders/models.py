"""Retained orders with immutable financial/contact snapshots and append-only history."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.orders.status import Status

_STATUS_VALUES = (
    "'pending', 'accepted', 'preparing', 'out_for_delivery', 'delivered', 'rejected', 'cancelled'"
)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "customer_id", "idempotency_key", name="uq_orders_customer_id_idempotency_key"
        ),
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="status_values"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="request_hash_format"),
        CheckConstraint(
            "subtotal_minor >= 0 AND subtotal_minor <= 9007199254740991", name="subtotal_bounds"
        ),
        CheckConstraint(
            "delivery_fee_minor >= 0 AND delivery_fee_minor <= 9007199254740991",
            name="delivery_fee_bounds",
        ),
        CheckConstraint(
            "total_minor >= 0 AND total_minor <= 9007199254740991", name="total_bounds"
        ),
        CheckConstraint(
            "total_minor = subtotal_minor + delivery_fee_minor", name="total_arithmetic"
        ),
        CheckConstraint(
            "char_length(btrim(delivery_address_line1)) > 0 "
            "AND char_length(delivery_address_line1) <= 200",
            name="address_line1_bounds",
        ),
        CheckConstraint(
            "delivery_address_line2 IS NULL OR (char_length(btrim(delivery_address_line2)) > 0 "
            "AND char_length(delivery_address_line2) <= 200)",
            name="address_line2_bounds",
        ),
        CheckConstraint(
            "char_length(btrim(delivery_postcode)) > 0 AND char_length(delivery_postcode) <= 32",
            name="postcode_bounds",
        ),
        CheckConstraint(
            "char_length(btrim(contact_phone)) > 0 AND char_length(contact_phone) <= 32",
            name="phone_bounds",
        ),
        CheckConstraint("notes IS NULL OR char_length(notes) <= 2000", name="notes_bounds"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    currency: Mapped[str] = mapped_column(Text)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger)
    delivery_fee_minor: Mapped[int] = mapped_column(BigInteger)
    total_minor: Mapped[int] = mapped_column(BigInteger)
    paid: Mapped[bool] = mapped_column(Boolean)
    delivery_address_line1: Mapped[str] = mapped_column(Text)
    delivery_address_line2: Mapped[str | None] = mapped_column(Text)
    delivery_postcode: Mapped[str] = mapped_column(Text)
    contact_phone: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid)
    request_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __mapper_args__ = {"eager_defaults": True}

    @property
    def refund_owed(self) -> bool:
        return self.paid and self.status in {Status.REJECTED, Status.CANCELLED}


Index("ix_orders_customer_created", Order.customer_id, Order.created_at.desc(), Order.id.desc())
Index("ix_orders_restaurant_created", Order.restaurant_id, Order.created_at.desc(), Order.id.desc())
Index(
    "ix_orders_restaurant_active",
    Order.restaurant_id,
    Order.status,
    postgresql_where=text("status IN ('pending', 'accepted', 'preparing', 'out_for_delivery')"),
)


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "menu_item_id", name="uq_order_lines_order_id_menu_item_id"),
        CheckConstraint("quantity BETWEEN 1 AND 20", name="quantity_bounds"),
        CheckConstraint(
            "unit_price_minor > 0 AND unit_price_minor <= 9007199254740991",
            name="unit_price_bounds",
        ),
        CheckConstraint(
            "original_unit_price_minor > 0 AND original_unit_price_minor <= 9007199254740991",
            name="original_price_bounds",
        ),
        CheckConstraint(
            "unit_price_minor <= original_unit_price_minor", name="charged_price_bounds"
        ),
        CheckConstraint(
            "line_total_minor > 0 AND line_total_minor <= 9007199254740991",
            name="line_total_bounds",
        ),
        CheckConstraint(
            "line_total_minor = unit_price_minor::numeric * quantity", name="line_arithmetic"
        ),
        CheckConstraint(
            "char_length(btrim(item_name)) > 0 AND char_length(item_name) <= 200",
            name="item_name_bounds",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    order_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), index=True
    )
    menu_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("menu_items.id", ondelete="RESTRICT")
    )
    item_name: Mapped[str] = mapped_column(Text)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger)
    original_unit_price_minor: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total_minor: Mapped[int] = mapped_column(BigInteger)
    __mapper_args__ = {"eager_defaults": True}


class OrderStatusChange(Base):
    __tablename__ = "order_status_changes"
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({_STATUS_VALUES})", name="from_status_values"
        ),
        CheckConstraint(f"to_status IN ({_STATUS_VALUES})", name="to_status_values"),
        CheckConstraint("actor_role IN ('customer', 'staff', 'admin')", name="actor_role_values"),
        CheckConstraint(
            "reason IS NULL OR (char_length(btrim(reason)) > 0 AND char_length(reason) <= 1000)",
            name="reason_bounds",
        ),
        CheckConstraint(
            "from_status IS NOT NULL OR (to_status = 'pending' "
            "AND actor_role = 'customer' AND reason IS NULL)",
            name="initial_shape",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    order_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="RESTRICT"))
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __mapper_args__ = {"eager_defaults": True}


Index(
    "ix_order_status_changes_order_created",
    OrderStatusChange.order_id,
    OrderStatusChange.created_at,
    OrderStatusChange.id,
)
Index(
    "uq_order_status_changes_initial",
    OrderStatusChange.order_id,
    unique=True,
    postgresql_where=text("from_status IS NULL"),
)
