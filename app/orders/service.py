"""Atomic mock-paid checkout with stable, customer-scoped idempotent replay."""

from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import Forbidden, NotFound
from app.menu import service as menu
from app.orders import repository
from app.orders.errors import DeliveryAddressRequired, IdempotencyKeyReused, InvalidOrderPricing
from app.orders.idempotency import request_hash
from app.orders.models import Order, OrderLine, OrderStatusChange
from app.orders.pagination import OrderCursor
from app.orders.pricing import price_order
from app.orders.schemas import (
    ActiveOrders,
    AddressSnapshot,
    CreationReceipt,
    OrderCreateIn,
    OrderDetail,
    OrderLineOut,
    OrderListQuery,
    OrderPage,
    OrderSnapshot,
    OrderSummary,
    StatusChangeOut,
    creation_receipt,
)
from app.orders.state_machine import initial_status_change
from app.payments.errors import PaymentDeclined, PaymentUnavailable
from app.payments.gateway import PaymentGateway, PaymentOutcome
from app.restaurants import service as restaurants
from app.users import service as users
from app.users.models import User
from app.users.roles import Role


@dataclass(frozen=True)
class PlacedOrder:
    receipt: CreationReceipt
    replayed: bool


def _receipt(session: Session, order: Order) -> CreationReceipt:
    initial = repository.get_initial_change(session, order.id)
    if initial is None:
        raise RuntimeError("Order is missing its initial status change")
    snapshot = OrderSnapshot(
        id=order.id,
        restaurant_id=order.restaurant_id,
        paid=order.paid,
        delivery_address=AddressSnapshot(
            address_line1=order.delivery_address_line1,
            address_line2=order.delivery_address_line2,
            postcode=order.delivery_postcode,
            phone=order.contact_phone,
        ),
        notes=order.notes,
        lines=tuple(
            OrderLineOut.model_validate(line) for line in repository.list_lines(session, order.id)
        ),
        currency=order.currency,
        subtotal_minor=order.subtotal_minor,
        delivery_fee_minor=order.delivery_fee_minor,
        total_minor=order.total_minor,
        created_at=order.created_at,
    )
    return creation_receipt(snapshot, StatusChangeOut.model_validate(initial))


def _replay(session: Session, order: Order, digest: str) -> PlacedOrder:
    if order.request_hash != digest:
        raise IdempotencyKeyReused()
    return PlacedOrder(_receipt(session, order), replayed=True)


def place_order(
    session: Session,
    customer_id: int,
    key: UUID,
    request: OrderCreateIn,
    currency: str,
    gateway: PaymentGateway,
) -> PlacedOrder:
    """The authenticated customer is checked by the router; this service owns one commit.

    Replays read snapshots only. For new attempts every feature shares this Session;
    the unique order insert is flushed before any gateway call. This transaction
    design is safe only for the mock payment seam, not real external providers.
    """
    digest = request_hash(request)
    try:
        existing = repository.get_by_customer_key(session, customer_id, key)
        if existing is not None:
            return _replay(session, existing, digest)

        restaurant = restaurants.get_for_ordering(session, request.restaurant_id)
        items = menu.get_orderable_items(
            session, request.restaurant_id, [line.menu_item_id for line in request.lines]
        )
        address = request.delivery_address
        if address is None:
            address = users.get_saved_address(session, customer_id)
        if address is None:
            raise DeliveryAddressRequired()
        try:
            priced = price_order(items, request.lines, restaurant.delivery_fee_minor, currency)
        except ValidationError as exc:
            raise InvalidOrderPricing(
                exc.errors(include_url=False, include_context=False, include_input=False)
            ) from None

        initial = initial_status_change(Role.CUSTOMER)
        order = Order(
            customer_id=customer_id,
            restaurant_id=restaurant.id,
            status=initial.to_status.value,
            currency=priced.currency,
            paid=True,
            subtotal_minor=priced.subtotal_minor,
            delivery_fee_minor=priced.delivery_fee_minor,
            total_minor=priced.total_minor,
            delivery_address_line1=address.address_line1,
            delivery_address_line2=address.address_line2,
            delivery_postcode=address.postcode,
            contact_phone=address.phone,
            notes=request.notes,
            idempotency_key=key,
            request_hash=digest,
        )
        try:
            repository.add_order(session, order)
        except IntegrityError as exc:
            if (
                getattr(exc.orig, "sqlstate", None) != "23505"
                or exc.orig.diag.constraint_name != "uq_orders_customer_id_idempotency_key"
            ):
                raise
            # The competing insert waits for the winner's commit. Discard the
            # failed transaction before reading that winner in a fresh one.
            session.rollback()
            winner = repository.get_by_customer_key(session, customer_id, key)
            if winner is None:
                raise
            return _replay(session, winner, digest)

        repository.add_lines(
            session, [OrderLine(order_id=order.id, **line.model_dump()) for line in priced.lines]
        )
        repository.append_status_change(
            session,
            OrderStatusChange(
                order_id=order.id,
                from_status=None,
                to_status=initial.to_status.value,
                actor_user_id=customer_id,
                actor_role=initial.actor_role.value,
                reason=initial.reason,
            ),
        )
        result = gateway.create_payment(order.id, priced.total_minor, priced.currency, key)
        if result.outcome == PaymentOutcome.DECLINED:
            raise PaymentDeclined()
        if result.outcome == PaymentOutcome.UNAVAILABLE:
            raise PaymentUnavailable()
        if result.outcome != PaymentOutcome.PAID:
            raise RuntimeError("Payment gateway returned an unsupported outcome")

        # Construct/validate the full response before committing, so serialization
        # invariant failures also roll back. paid=True is never committed on failure.
        receipt = _receipt(session, order)
        session.commit()
        return PlacedOrder(receipt, replayed=False)
    except Exception:
        session.rollback()
        raise


def _detail(session: Session, order: Order) -> OrderDetail:
    snapshot = _receipt(session, order)
    return OrderDetail(
        **snapshot.model_dump(exclude={"status"}),
        customer_id=order.customer_id,
        status=order.status,
        updated_at=order.updated_at,
        status_changes=tuple(
            StatusChangeOut.model_validate(change)
            for change in repository.list_status_changes(session, order.id)
        ),
    )


def get_order(session: Session, user: User, order_id: UUID) -> OrderDetail:
    order = repository.get_visible(session, user, order_id)
    if order is None:
        raise NotFound()
    return _detail(session, order)


def list_orders(session: Session, user: User, query: OrderListQuery) -> OrderPage | ActiveOrders:
    if query.active == "true":
        if user.role != Role.STAFF:
            raise Forbidden()
        return ActiveOrders(
            items=[
                OrderSummary.model_validate(row)
                for row in repository.list_visible(session, user, active=True)
            ]
        )
    cursor = OrderCursor.decode(query.cursor) if query.cursor is not None else None
    rows = repository.list_visible(session, user, limit=query.limit + 1, cursor=cursor)
    items = rows[: query.limit]
    next_cursor = (
        OrderCursor(items[-1].created_at, items[-1].id).encode()
        if len(rows) > query.limit
        else None
    )
    return OrderPage(
        items=[OrderSummary.model_validate(row) for row in items], next_cursor=next_cursor
    )
