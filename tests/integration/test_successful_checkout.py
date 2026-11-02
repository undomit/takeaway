"""Successful checkout persists a complete paid order using real request transactions."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.menu.models import MenuCategory, MenuItem
from app.orders.models import Order, OrderLine, OrderStatusChange
from app.payments.dependencies import get_payment_gateway
from app.users.models import User
from tests.factories import create_restaurant, login_token
from tests.fakes import RecordingPaymentGateway

# The committed-data marker is also required for serial runs and owner cleanup.
pytestmark = [pytest.mark.integration, pytest.mark.concurrency]


@pytest.fixture
def settings(settings):
    """A nondefault currency catches accidental hard-coded EUR pricing/payment."""
    return settings.model_copy(update={"platform_currency": "GBP"})


@pytest.mark.parametrize("address_source", ["saved", "one-off"])
def test_successful_checkout_copies_and_commits_order_snapshots(
    committed_session_factory, database_client, address_source
):
    with committed_session_factory() as session:
        restaurant = create_restaurant(session, delivery_fee_minor=250, is_accepting_orders=True)
        category = MenuCategory(restaurant_id=restaurant.id, name="Lunch")
        session.add(category)
        session.flush()
        soup = MenuItem(
            restaurant_id=restaurant.id,
            category_id=category.id,
            name="Example Soup",
            price_minor=1250,
            sale_price_minor=1063,
        )
        drink = MenuItem(
            restaurant_id=restaurant.id,
            category_id=category.id,
            name="Example Drink",
            price_minor=200,
        )
        session.add_all([soup, drink])
        session.commit()
        restaurant_id, soup_id, drink_id = restaurant.id, soup.id, drink.id

    saved_address = {
        "address_line1": "10 Example Street",
        "address_line2": "Flat 2",
        "postcode": "AB1 2CD",
        "phone": "+441234567890",
    }
    one_off_address = {
        "address_line1": "20 Other Street",
        "postcode": "XY9 8ZZ",
        "phone": "+449876543210",
    }
    expected_address = (
        saved_address if address_source == "saved" else {**one_off_address, "address_line2": None}
    )
    key = uuid4()
    notes = " Leave at reception "
    gateway = RecordingPaymentGateway()

    # No session/auth overrides: each request gets the normal runtime Session.
    with database_client() as client:
        client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
        registration = client.post(
            "/api/v1/auth/register",
            json={
                "email": "checkout@example.test",
                "full_name": "Checkout Customer",
                "password": "checkout-test-passphrase",
            },
        )
        assert registration.status_code == 201, registration.text
        customer_id = registration.json()["id"]
        token = login_token(client, "checkout@example.test", "checkout-test-passphrase")
        headers = {"Authorization": f"Bearer {token}"}
        profile = client.patch("/api/v1/me", headers=headers, json={"saved_address": saved_address})
        assert profile.status_code == 200, profile.text
        assert profile.json()["saved_address"] == saved_address

        body = {
            "restaurant_id": restaurant_id,
            # Deliberately not in menu-ID order: output must sort persisted line IDs.
            "lines": [
                {"menu_item_id": drink_id, "quantity": 3},
                {"menu_item_id": soup_id, "quantity": 2},
            ],
            "notes": notes,
        }
        if address_source == "one-off":
            body["delivery_address"] = one_off_address
        response = client.post(
            "/api/v1/orders", headers={**headers, "Idempotency-Key": str(key)}, json=body
        )
        assert response.status_code == 201, response.text
        assert "Idempotent-Replayed" not in response.headers
        receipt = response.json()
        assert client.get("/api/v1/me", headers=headers).json() == profile.json()

    # An independent Session after the HTTP Session closes proves the commit.
    with committed_session_factory() as observer:
        orders = list(observer.scalars(select(Order)))
        lines = list(observer.scalars(select(OrderLine).order_by(OrderLine.id)))
        changes = list(observer.scalars(select(OrderStatusChange)))
        assert len(orders) == 1 and len(lines) == 2 and len(changes) == 1
        order, change = orders[0], changes[0]
        order_id = UUID(receipt["id"])
        assert order_id.version == 4 and order.id == order_id
        assert (order.customer_id, order.restaurant_id, order.status, order.paid) == (
            customer_id,
            restaurant_id,
            "pending",
            True,
        )
        assert (
            order.currency,
            order.subtotal_minor,
            order.delivery_fee_minor,
            order.total_minor,
        ) == (
            "GBP",
            2726,
            250,
            2976,
        )
        assert order.idempotency_key == key and order.notes == notes
        assert {
            "address_line1": order.delivery_address_line1,
            "address_line2": order.delivery_address_line2,
            "postcode": order.delivery_postcode,
            "phone": order.contact_phone,
        } == expected_address
        assert order.created_at.utcoffset() == timedelta(0)
        assert order.updated_at == order.created_at

        expected_by_item = {
            soup_id: {
                "menu_item_id": soup_id,
                "item_name": "Example Soup",
                "unit_price_minor": 1063,
                "original_unit_price_minor": 1250,
                "quantity": 2,
                "line_total_minor": 2126,
            },
            drink_id: {
                "menu_item_id": drink_id,
                "item_name": "Example Drink",
                "unit_price_minor": 200,
                "original_unit_price_minor": 200,
                "quantity": 3,
                "line_total_minor": 600,
            },
        }
        assert {line.menu_item_id for line in lines} == {soup_id, drink_id}
        for line in lines:
            assert line.order_id == order.id
            assert {
                field: getattr(line, field) for field in expected_by_item[line.menu_item_id]
            } == expected_by_item[line.menu_item_id]
        assert (
            change.order_id,
            change.from_status,
            change.to_status,
            change.actor_user_id,
            change.actor_role,
            change.reason,
        ) == (order.id, None, "pending", customer_id, "customer", None)
        assert change.created_at == order.created_at
        user = observer.get(User, customer_id)
        assert (user.address_line1, user.address_line2, user.postcode, user.phone) == (
            saved_address["address_line1"],
            saved_address["address_line2"],
            saved_address["postcode"],
            saved_address["phone"],
        )
        assert receipt == {
            "id": str(order.id),
            "restaurant_id": restaurant_id,
            "status": "pending",
            "paid": True,
            "currency": "GBP",
            "delivery_address": expected_address,
            "notes": notes,
            "lines": [{"id": line.id, **expected_by_item[line.menu_item_id]} for line in lines],
            "subtotal_minor": 2726,
            "delivery_fee_minor": 250,
            "total_minor": 2976,
            "created_at": order.created_at.isoformat(timespec="microseconds").replace(
                "+00:00", "Z"
            ),
        }
    assert gateway.calls == [(order_id, 2976, "GBP", key)]
    assert [line["id"] for line in receipt["lines"]] == sorted(
        line["id"] for line in receipt["lines"]
    )
    for field in ("subtotal_minor", "delivery_fee_minor", "total_minor"):
        assert type(receipt[field]) is int
    for line in receipt["lines"]:
        for field in ("unit_price_minor", "original_unit_price_minor", "line_total_minor"):
            assert type(line[field]) is int
