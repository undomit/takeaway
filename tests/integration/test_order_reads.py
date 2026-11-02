"""Scope precedes pagination; kitchen polling is complete and read-only."""

from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.orders.models import Order
from app.orders.pagination import OrderCursor
from app.restaurants.pagination import RestaurantCursor
from tests.order_support import ok, place, world

pytestmark = pytest.mark.integration


def test_detail_and_history_apply_customer_restaurant_and_admin_scope(client, db_session):
    data = world(client, db_session)
    orders = [
        ok(place(client, data), 201),
        ok(place(client, data, customer="customer_b"), 201),
        ok(place(client, data, customer="customer_b", restaurant=1), 201),
    ]
    expected = {
        "customer_a": {0},
        "customer_b": {1, 2},
        "staff_a": {0, 1},
        "staff_b": {2},
        "admin": {0, 1, 2},
    }
    for role, indices in expected.items():
        headers = data.headers[role]
        page = ok(client.get("/api/v1/orders", headers=headers))
        assert {row["id"] for row in page["items"]} == {orders[i]["id"] for i in indices}
        assert page["next_cursor"] is None
        for index, order in enumerate(orders):
            response = client.get(f"/api/v1/orders/{order['id']}", headers=headers)
            if index not in indices:
                assert response.status_code == 404 and response.json()["code"] == "not_found"
            else:
                detail = ok(response)
                assert detail["delivery_address"] == order["delivery_address"]
                assert detail["lines"] == order["lines"]
                assert detail["status"] == "pending" and not detail["refund_owed"]
                assert len(detail["status_changes"]) == 1
                assert detail["status_changes"][0]["actor_user_id"] == detail["customer_id"]
        missing = client.get(f"/api/v1/orders/{uuid4()}", headers=headers)
        assert missing.status_code == 404 and missing.json()["code"] == "not_found"
    assert client.get("/api/v1/orders").status_code == 401
    assert client.get(f"/api/v1/orders/{orders[0]['id']}").status_code == 401


def test_keyset_ties_strict_queries_and_complete_read_only_polling(client, db_session):
    data = world(client, db_session)
    # PostgreSQL now() is fixed for the surrounding fixture transaction: all ties.
    receipts = [ok(place(client, data), 201) for _ in range(53)]
    expected = sorted([row["id"] for row in receipts], reverse=True)
    seen, cursor = [], None
    while True:
        page = ok(
            client.get(
                "/api/v1/orders",
                headers=data.headers["customer_a"],
                params={"limit": 7} | ({"cursor": cursor} if cursor else {}),
            )
        )
        assert all(
            "delivery_address" not in row and "status_changes" not in row for row in page["items"]
        )
        seen.extend(row["id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == expected
    headers = data.headers["staff_a"]
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        for _ in range(2):
            active = ok(client.get("/api/v1/orders?active=true", headers=headers))
            assert set(active) == {"items"}
            assert [row["id"] for row in active["items"]] == expected
            ok(client.get(f"/api/v1/orders/{expected[0]}", headers=headers))
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE"}
    for role in ("customer_a", "admin"):
        assert (
            client.get("/api/v1/orders?active=true", headers=data.headers[role]).status_code == 403
        )
    order = db_session.scalar(select(Order))
    token = OrderCursor(order.created_at, order.id).encode()
    foreign = RestaurantCursor(order.created_at, 1).encode()
    for query in (
        "active=True",
        "active=1",
        "active=true&limit=50",
        "active=true&cursor=",
        "updated_since=now",
        "customer_id=1",
        "status=pending",
        "limit=0",
        "limit=101",
        "cursor=",
        "cursor=bad",
        f"cursor={token}=",
        f"cursor={foreign}",
    ):
        response = client.get(f"/api/v1/orders?{query}", headers=headers)
        assert response.status_code == 422, (query, response.text)
    assert client.get("/api/v1/orders?active=false&limit=1", headers=headers).status_code == 200
