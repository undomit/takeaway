"""Failed attempts reserve nothing; successful replay never re-resolves mutable inputs."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.orders.models import Order, OrderLine, OrderStatusChange
from app.payments.dependencies import get_payment_gateway
from app.payments.gateway import PaymentOutcome, PaymentResult
from tests.order_support import ADDRESS, error, ok, place, world

pytestmark = pytest.mark.integration


class ControlledGateway:
    def __init__(self):
        self.outcome = PaymentOutcome.PAID
        self.calls = []

    def create_payment(self, *args):
        self.calls.append(args)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return PaymentResult(self.outcome)


def count_rows(session):
    return tuple(
        session.scalar(select(func.count()).select_from(model))
        for model in (Order, OrderLine, OrderStatusChange)
    )


def test_payment_failures_roll_back_every_row_and_do_not_reserve_the_key(client, db_session):
    data, gateway, key = world(client, db_session), ControlledGateway(), uuid4()
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    for outcome, status, code in (
        (PaymentOutcome.DECLINED, 409, "payment_declined"),
        (PaymentOutcome.UNAVAILABLE, 503, "payment_unavailable"),
    ):
        gateway.outcome = outcome
        error(place(client, data, key=key), status, code)
        assert count_rows(db_session) == (0, 0, 0)
    gateway.outcome = RuntimeError("gateway failure")
    with pytest.raises(RuntimeError, match="gateway failure"):
        place(client, data, key=key)
    assert count_rows(db_session) == (0, 0, 0)
    gateway.outcome = PaymentOutcome.PAID
    receipt = ok(place(client, data, key=key), 201)
    assert count_rows(db_session) == (1, 1, 1)
    assert len(gateway.calls) == 4
    assert gateway.calls[-1][1:] == (2750, "EUR", key)
    assert ok(place(client, data, key=key), 201) == receipt
    assert len(gateway.calls) == 4


def test_checkout_failure_contract_and_replay_after_mutable_inputs_change(client, db_session):
    data, gateway, key = world(client, db_session), ControlledGateway(), uuid4()
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    sh, ch, ah = (data.headers[role] for role in ("staff_a", "customer_a", "admin"))
    rid, mid = data.restaurants[0], data.items[0]
    root = f"/api/v1/restaurants/{rid}"
    item_url = root + f"/menu/items/{mid}"
    body = {"restaurant_id": rid, "lines": [{"menu_item_id": mid, "quantity": 2}]}
    error(client.post("/api/v1/orders", headers=ch, json=body), 400, "idempotency_key_required")
    for bad in (
        "",
        "not-a-uuid",
        "00000000-0000-0000-0000-000000000000",
        str(key).replace("-", ""),
    ):
        error(client.post("/api/v1/orders", headers=ch | {"Idempotency-Key": bad}, json=body), 422)
    error(
        client.post(
            "/api/v1/orders",
            headers=[*ch.items(), ("Idempotency-Key", str(key)), ("Idempotency-Key", str(key))],
            json=body,
        ),
        422,
    )
    for lines in ([{"menu_item_id": mid, "quantity": value}] for value in (0, 21, True, 1.0, "1")):
        error(place(client, data, key=key, lines=lines), 422)
    for extra in (
        {"paid": True},
        {"total_minor": 1},
        {"status": "delivered"},
        {"delivery_address": {"address_line1": "Partial"}},
        {"lines": body["lines"] * 2},
    ):
        error(place(client, data, key=key, **extra), 422)
    ok(client.patch(root + "/accepting-orders", headers=sh, json={"is_accepting_orders": False}))
    error(place(client, data, key=key), 409, "restaurant_not_accepting_orders")
    ok(client.patch(root + "/accepting-orders", headers=sh, json={"is_accepting_orders": True}))
    for foreign in (data.items[1], 9223372036854775807):
        error(
            place(client, data, key=key, lines=[{"menu_item_id": foreign, "quantity": 1}]),
            409,
            "item_unavailable",
        )
    ok(client.patch(item_url, headers=sh, json={"is_available": False}))
    menu = ok(client.get(root + "/menu"))
    assert not menu["categories"][0]["items"][0]["is_available"]
    error(place(client, data, key=key), 409, "item_unavailable")
    ok(client.patch(item_url, headers=sh, json={"is_available": True}))
    ok(client.patch("/api/v1/me", headers=ch, json={"saved_address": None}))
    error(place(client, data, key=key), 422, "delivery_address_required")
    ok(client.patch("/api/v1/me", headers=ch, json={"saved_address": ADDRESS}))
    ok(client.patch(root, headers=ah, json={"delivery_fee_minor": 9007199254740991}))
    error(place(client, data, key=key), 422)
    ok(client.patch(root, headers=ah, json={"delivery_fee_minor": 250}))
    assert gateway.calls == [] and count_rows(db_session) == (0, 0, 0)
    receipt = ok(place(client, data, key=key), 201)
    # Defaults and object-member order are canonical, while notes/line order are intent.
    replay_body = {
        "notes": None,
        "delivery_address": None,
        "lines": body["lines"],
        "restaurant_id": rid,
    }
    replay = client.post(
        "/api/v1/orders", headers=ch | {"Idempotency-Key": str(key).upper()}, json=replay_body
    )
    assert ok(replay, 201) == receipt and replay.headers["Idempotent-Replayed"] == "true"
    for extra in (
        {"notes": ""},
        {"delivery_address": ADDRESS},
        {"lines": [{"menu_item_id": mid, "quantity": 3}]},
    ):
        error(place(client, data, key=key, **extra), 422, "idempotency_key_reused")
    ok(client.post(item_url + "/archive", headers=sh))
    error(place(client, data), 409, "item_unavailable")
    ok(client.patch(root + "/accepting-orders", headers=sh, json={"is_accepting_orders": False}))
    ok(client.patch("/api/v1/me", headers=ch, json={"saved_address": None}))
    assert ok(place(client, data, key=key), 201) == receipt
    assert count_rows(db_session) == (1, 1, 1) and len(gateway.calls) == 1


def test_sale_price_validation_and_atomic_price_updates(client, db_session):
    data = world(client, db_session)
    sh = data.headers["staff_a"]
    url = f"/api/v1/restaurants/{data.restaurants[0]}/menu/items/{data.items[0]}"
    original_menu = ok(client.get(f"/api/v1/restaurants/{data.restaurants[0]}/menu"))
    for body in (
        {},
        {"percentage_off": "0"},
        {"percentage_off": "100"},
        {"percentage_off": 15},
        {"percentage_off": "15.001"},
        {"sale_price_minor": 1250},
        {"sale_price_minor": 0},
        {"sale_price_minor": True},
        {"sale_price_minor": 1000.0},
        {"sale_price_minor": 1000, "percentage_off": "15"},
    ):
        error(client.put(url + "/sale-price", headers=sh, json=body), 422)
    assert ok(client.get(f"/api/v1/restaurants/{data.restaurants[0]}/menu")) == original_menu
    assert (
        ok(client.put(url + "/sale-price", headers=sh, json={"percentage_off": "15.00"}))[
            "sale_price_minor"
        ]
        == 1063
    )
    error(client.patch(url, headers=sh, json={"name": "Must roll back", "price_minor": 1000}), 422)
    current = ok(client.get(f"/api/v1/restaurants/{data.restaurants[0]}/menu"))["categories"][0][
        "items"
    ][0]
    assert current["name"] == "Original Soup" and current["price_minor"] == 1250
    changed = ok(
        client.patch(url, headers=sh, json={"price_minor": 1000, "sale_price_minor": None})
    )
    assert changed["price_minor"] == 1000 and changed["sale_price_minor"] is None
