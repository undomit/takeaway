"""Independent design-table oracles for the previously deferred pure behavior."""

import base64
import json
from datetime import UTC, datetime
from itertools import product
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.menu.errors import InvalidSalePrice
from app.menu.service import percentage_to_sale_price
from app.orders.errors import InvalidTransition, ReasonRequired, TransitionNotPermitted
from app.orders.idempotency import request_hash
from app.orders.pagination import OrderCursor
from app.orders.pricing import price_order
from app.orders.schemas import OrderCreateIn
from app.orders.state_machine import check_transition
from app.orders.status import Status
from app.users.roles import Role


def test_all_147_status_role_pairs_against_the_design_table():
    # This oracle is deliberately independent of the implementation's rule map.
    allowed = {
        ("pending", "accepted"): ("staff", False),
        ("pending", "rejected"): ("staff", True),
        ("pending", "cancelled"): ("customer", False),
        ("accepted", "preparing"): ("staff", False),
        ("accepted", "cancelled"): ("staff", True),
        ("preparing", "out_for_delivery"): ("staff", False),
        ("preparing", "cancelled"): ("staff", True),
        ("out_for_delivery", "delivered"): ("staff", False),
    }
    for source, target, role in product(Status, Status, Role):
        case = (source, target, role)
        rule = allowed.get((source, target))
        if rule is None:
            with pytest.raises(InvalidTransition):
                check_transition(*case, reason="Reason")
        elif role != rule[0]:
            with pytest.raises(TransitionNotPermitted):
                check_transition(*case, reason="Reason")
        else:
            checked = check_transition(*case, reason="  Reason  ")
            assert (checked.from_status, checked.to_status, checked.actor_role, checked.reason) == (
                source,
                target,
                role,
                "Reason",
            )
            if rule[1]:
                for reason in (None, "", "   "):
                    with pytest.raises(ReasonRequired):
                        check_transition(*case, reason=reason)


def test_integer_pricing_snapshots_bounds_and_invalid_selections():
    items = [
        SimpleNamespace(id=1, name="Sale", price_minor=1250, sale_price_minor=1063),
        SimpleNamespace(id=2, name="Regular", price_minor=500, sale_price_minor=None),
    ]
    lines = [{"menu_item_id": 1, "quantity": 2}, {"menu_item_id": 2, "quantity": 3}]
    result = price_order(items, lines, 250, "EUR")
    assert (result.subtotal_minor, result.delivery_fee_minor, result.total_minor) == (
        3626,
        250,
        3876,
    )
    assert result.lines[0].unit_price_minor == 1063
    assert result.lines[0].original_unit_price_minor == 1250
    assert result.lines[1].unit_price_minor == 500
    for line in result.lines:
        assert all(
            type(getattr(line, field)) is int
            for field in (
                "unit_price_minor",
                "original_unit_price_minor",
                "line_total_minor",
                "quantity",
            )
        )
    assert all(
        type(getattr(result, field)) is int
        for field in ("subtotal_minor", "delivery_fee_minor", "total_minor")
    )
    for quantity in (0, 21, True, 1.0, "1"):
        with pytest.raises(ValidationError):
            price_order(items, [{"menu_item_id": 1, "quantity": quantity}], 0, "EUR")
    for selections, fee in (
        ([], 0),
        (lines + lines, 0),
        (lines, 9007199254740991),
        ([{"menu_item_id": 3, "quantity": 1}], 0),
    ):
        with pytest.raises(ValidationError):
            price_order(items, selections, fee, "EUR")
    assert percentage_to_sale_price(1250, "15.00") == 1063
    for price, percentage in ((1, "99.99"), (1, "0.01")):
        with pytest.raises(InvalidSalePrice):
            percentage_to_sale_price(price, percentage)


def test_canonical_hash_expands_defaults_but_preserves_line_order_and_intent():
    lines = [{"menu_item_id": 1, "quantity": 2}, {"menu_item_id": 2, "quantity": 1}]
    body = {"restaurant_id": 1, "lines": lines}
    digest = request_hash(OrderCreateIn.model_validate(body))
    assert digest == request_hash(
        OrderCreateIn.model_validate(
            {"notes": None, "delivery_address": None, "lines": lines, "restaurant_id": 1}
        )
    )
    for replacement in ({"lines": list(reversed(lines))}, {"notes": ""}, {"restaurant_id": 2}):
        assert digest != request_hash(OrderCreateIn.model_validate(body | replacement))


def test_cursor_rejects_noncanonical_or_wrong_typed_positions():
    cursor = OrderCursor(datetime(2026, 11, 2, tzinfo=UTC), uuid4())
    assert OrderCursor.decode(cursor.encode()) == cursor
    decoded = {
        "v": 1,
        "resource": "orders",
        "created_at": "2026-11-02T00:00:00.000000Z",
        "id": str(cursor.id),
    }

    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    bad = [
        "",
        "x" * 1025,
        cursor.encode() + "=",
        "_w",
        encode([]),
        encode({}),
        base64.urlsafe_b64encode(b'{"v":1,"v":1}').decode().rstrip("="),
    ]
    bad.extend(
        encode(decoded | replacement)
        for replacement in (
            {"v": True},
            {"v": 2},
            {"resource": "restaurants"},
            {"extra": 1},
            {"id": 1},
            {"id": str(cursor.id).upper()},
            {"id": "00000000-0000-0000-0000-000000000000"},
            {"created_at": "2026-11-02T00:00:00Z"},
            {"created_at": "2026-02-30T00:00:00.000000Z"},
            {"created_at": "2026-11-02T00:00:00.000000+00:00"},
        )
    )
    for token in bad:
        with pytest.raises(ValueError, match="Invalid order cursor"):
            OrderCursor.decode(token)
