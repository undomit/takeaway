"""Shared API setup: only the bootstrap admin is inserted directly."""

from types import SimpleNamespace
from uuid import uuid4

from app.security import hash_password
from app.users.roles import Role
from tests.factories import create_user, login_token

PASSWORD = "example-passphrase"
ADDRESS = {"address_line1": "10 Original Street", "postcode": "AB1", "phone": "+441234"}


def auth(client, email):
    return {"Authorization": f"Bearer {login_token(client, email, PASSWORD)}"}


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def world(client, session):
    admin = create_user(
        session, email="admin@example.test", role=Role.ADMIN, password_hash=hash_password(PASSWORD)
    )
    session.commit()
    headers = {"admin": auth(client, admin.email)}
    ids = {"admin": admin.id}
    restaurants, categories, items = [], [], []
    for suffix in ("a", "b"):
        customer = ok(
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"customer-{suffix}@example.test",
                    "full_name": f"Customer {suffix}",
                    "password": PASSWORD,
                },
            ),
            201,
        )
        ids[f"customer_{suffix}"] = customer["id"]
        headers[f"customer_{suffix}"] = auth(client, customer["email"])
        ok(
            client.patch(
                "/api/v1/me", headers=headers[f"customer_{suffix}"], json={"saved_address": ADDRESS}
            )
        )
        restaurant = ok(
            client.post(
                "/api/v1/restaurants",
                headers=headers["admin"],
                json={
                    "name": f"Restaurant {suffix}",
                    "slug": f"restaurant-{suffix}",
                    "delivery_fee_minor": 250,
                },
            ),
            201,
        )
        rid = restaurant["id"]
        restaurants.append(rid)
        staff = ok(
            client.post(
                "/api/v1/users",
                headers=headers["admin"],
                json={
                    "email": f"staff-{suffix}@example.test",
                    "full_name": f"Staff {suffix}",
                    "password": PASSWORD,
                    "restaurant_id": rid,
                },
            ),
            201,
        )
        ids[f"staff_{suffix}"] = staff["id"]
        headers[f"staff_{suffix}"] = auth(client, staff["email"])
        sh = headers[f"staff_{suffix}"]
        ok(
            client.patch(
                f"/api/v1/restaurants/{rid}/accepting-orders",
                headers=sh,
                json={"is_accepting_orders": True},
            )
        )
        category = ok(
            client.post(
                f"/api/v1/restaurants/{rid}/menu/categories", headers=sh, json={"name": "Main"}
            ),
            201,
        )
        categories.append(category["id"])
        item = ok(
            client.post(
                f"/api/v1/restaurants/{rid}/menu/items",
                headers=sh,
                json={
                    "category_id": category["id"],
                    "name": "Original Soup",
                    "price_minor": 1250,
                },
            ),
            201,
        )
        items.append(item["id"])
    return SimpleNamespace(
        headers=headers, ids=ids, restaurants=restaurants, categories=categories, items=items
    )


def place(client, data, *, customer="customer_a", restaurant=0, key=None, **extra):
    body = {
        "restaurant_id": data.restaurants[restaurant],
        "lines": [{"menu_item_id": data.items[restaurant], "quantity": 2}],
    } | extra
    headers = data.headers[customer] | {"Idempotency-Key": str(key or uuid4())}
    return client.post("/api/v1/orders", headers=headers, json=body)
