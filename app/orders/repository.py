"""Own-table order queries/inserts; never commits or accesses other features."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, false, func, select, tuple_, update
from sqlalchemy.orm import Session

from app.orders.models import Order, OrderLine, OrderStatusChange
from app.orders.pagination import OrderCursor
from app.orders.status import ACTIVE_STATUSES
from app.users.models import User
from app.users.roles import Role


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


def visible_to(user: User) -> Select[tuple[Order]]:
    """All read paths start here; cursors and filters can only narrow this scope."""
    query = select(Order)
    if user.role == Role.CUSTOMER:
        return query.where(Order.customer_id == user.id)
    if user.role == Role.STAFF:
        return query.where(Order.restaurant_id == user.restaurant_id)
    if user.role == Role.ADMIN:
        return query
    return query.where(false())


def get_visible(session: Session, user: User, order_id: UUID) -> Order | None:
    return session.scalar(visible_to(user).where(Order.id == order_id))


def list_visible(
    session: Session,
    user: User,
    *,
    limit: int | None = None,
    cursor: OrderCursor | None = None,
    active: bool = False,
) -> list[Order]:
    query = visible_to(user)
    if active:
        query = query.where(Order.status.in_(ACTIVE_STATUSES))
    if cursor is not None:
        query = query.where(tuple_(Order.created_at, Order.id) < (cursor.created_at, cursor.id))
    query = query.order_by(Order.created_at.desc(), Order.id.desc())
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def update_status(session: Session, order_id: UUID, expected: str, target: str) -> bool:
    result = session.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == expected)
        .values(status=target, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
