"""Own-table order queries/inserts; never commits or accesses other features."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.orders.models import Order, OrderLine, OrderStatusChange


def add_order(session: Session, order: Order) -> Order:
    session.add(order)
    session.flush()
    return order


def add_lines(session: Session, lines: Sequence[OrderLine]) -> None:
    session.add_all(lines)
    session.flush()


def append_status_change(session: Session, change: OrderStatusChange) -> OrderStatusChange:
    session.add(change)
    session.flush()
    return change


def get_by_id(session: Session, order_id: UUID) -> Order | None:
    return session.get(Order, order_id)


def get_by_customer_key(session: Session, customer_id: int, key: UUID) -> Order | None:
    return session.scalar(
        select(Order).where(Order.customer_id == customer_id, Order.idempotency_key == key)
    )


def list_lines(session: Session, order_id: UUID) -> list[OrderLine]:
    return list(
        session.scalars(
            select(OrderLine).where(OrderLine.order_id == order_id).order_by(OrderLine.id)
        )
    )


def list_status_changes(session: Session, order_id: UUID) -> list[OrderStatusChange]:
    return list(
        session.scalars(
            select(OrderStatusChange)
            .where(OrderStatusChange.order_id == order_id)
            .order_by(OrderStatusChange.created_at, OrderStatusChange.id)
        )
    )


def get_initial_change(session: Session, order_id: UUID) -> OrderStatusChange | None:
    return session.scalar(
        select(OrderStatusChange).where(
            OrderStatusChange.order_id == order_id, OrderStatusChange.from_status.is_(None)
        )
    )
