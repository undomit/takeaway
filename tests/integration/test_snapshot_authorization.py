"""Cross-feature API regressions with real registration, login and PostgreSQL."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.orders.models import OrderStatusChange
from tests.order_support import ADDRESS, PASSWORD, auth, error, ok, place, world

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("one_off", [False, True])
def test_financial_and_contact_snapshots_survive_all_later_edits(client, db_session, one_off):
    data = world(client, db_session)
    rid, mid = data.restaurants[0], data.items[0]
    sh, ch, ah = (data.headers[role] for role in ("staff_a", "customer_a", "admin"))
    item_url = f"/api/v1/restaurants/{rid}/menu/items/{mid}"
    sale = ok(client.put(item_url + "/sale-price", headers=sh, json={"percentage_off": "15.00"}))
    assert sale["sale_price_minor"] == 1063
    key = uuid4()
    supplied = ADDRESS | {"address_line1": "20 One-off Street", "phone": "+449999"}
    extra = {"delivery_address": supplied} if one_off else {}
    receipt = ok(place(client, data, key=key, **extra), 201)
    assert receipt["delivery_address"] == (supplied if one_off else ADDRESS) | {
        "address_line2": None
    }
    assert (
        ok(client.get("/api/v1/me", headers=ch))["saved_address"]["address_line1"]
        == ADDRESS["address_line1"]
    )
    line = receipt["lines"][0]
    assert line["item_name"] == "Original Soup"
    assert (
        line["unit_price_minor"],
        line["original_unit_price_minor"],
        line["quantity"],
        line["line_total_minor"],
    ) == (1063, 1250, 2, 2126)
    assert (receipt["subtotal_minor"], receipt["delivery_fee_minor"], receipt["total_minor"]) == (
        2126,
        250,
        2376,
    )
    assert receipt["currency"] == "EUR"
    url = f"/api/v1/orders/{receipt['id']}"
    initial_detail = ok(client.get(url, headers=ch))
    ok(
        client.patch(
            item_url,
            headers=sh,
            json={"name": "New Soup", "price_minor": 2000, "sale_price_minor": 1500},
        )
    )
    ok(client.patch(f"/api/v1/restaurants/{rid}", headers=ah, json={"delivery_fee_minor": 500}))
    changed_address = ADDRESS | {"address_line1": "30 New Saved Street", "phone": "+448888"}
    ok(client.patch("/api/v1/me", headers=ch, json={"saved_address": changed_address}))
    fresh = ok(place(client, data), 201)
    assert fresh["lines"][0]["item_name"] == "New Soup"
    assert fresh["lines"][0]["unit_price_minor"] == 1500
    assert fresh["lines"][0]["original_unit_price_minor"] == 2000
    assert fresh["delivery_fee_minor"] == 500 and fresh["total_minor"] == 3500
    assert fresh["delivery_address"]["address_line1"] == changed_address["address_line1"]
    assert ok(client.get(url, headers=ch)) == initial_detail
    ok(client.post(item_url + "/archive", headers=sh))
    ok(client.patch("/api/v1/me", headers=ch, json={"saved_address": None}))
    menu = ok(client.get(f"/api/v1/restaurants/{rid}/menu"))
    assert menu["categories"][0]["items"] == []
    assert ok(client.get(url, headers=ch)) == initial_detail
    ok(client.post(url + "/status-changes", headers=sh, json={"to_status": "accepted"}))
    replay = place(client, data, key=key, **extra)
    assert ok(replay, 201) == receipt and replay.headers["Idempotent-Replayed"] == "true"
    current = ok(client.get(url, headers=ch))
    assert current["status"] == "accepted" and len(current["status_changes"]) == 2
    assert {name: current[name] for name in receipt if name != "status"} == {
        name: receipt[name] for name in receipt if name != "status"
    }
    for method, suffix, body in (
        ("patch", "", {"name": "No"}),
        ("put", "/sale-price", {"sale_price_minor": 1000}),
    ):
        error(
            getattr(client, method)(item_url + suffix, headers=sh, json=body), 409, "item_archived"
        )
    assert ok(client.post(item_url + "/archive", headers=sh))["is_archived"]


@pytest.mark.parametrize("role", ["customer_a", "customer_b", "staff_a", "staff_b", "admin"])
def test_route_role_matrix_covers_every_menu_and_administration_boundary(client, db_session, role):
    data = world(client, db_session)
    h = data.headers[role]
    rid, mid, cid = data.restaurants[0], data.items[0], data.categories[0]
    root = f"/api/v1/restaurants/{rid}"
    # Public browsing ignores bearer identity and discloses no account/contact data.
    for headers in ({}, h, {"Authorization": "Bearer malformed"}):
        for path in ("/api/v1/restaurants", root, root + "/menu"):
            body = ok(client.get(path, headers=headers))
            assert "phone" not in str(body) and "password" not in str(body)
    profile = ok(client.get("/api/v1/me", headers=h))
    assert profile["id"] == data.ids[role]
    response = client.patch("/api/v1/me", headers=h, json={"full_name": "Updated Name"})
    if role.startswith("customer"):
        assert ok(response)["full_name"] == "Updated Name"
    else:
        error(response, 403, "forbidden")
    target = ok(
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "deactivate@example.test",
                "full_name": "Target",
                "password": PASSWORD,
            },
        ),
        201,
    )
    admin_ops = [
        (
            "post",
            "/api/v1/restaurants",
            {"name": "Third", "slug": "third", "delivery_fee_minor": 0},
            201,
        ),
        ("patch", root, {"delivery_fee_minor": 300}, 200),
        (
            "post",
            "/api/v1/users",
            {
                "email": "new-staff@example.test",
                "full_name": "New Staff",
                "password": PASSWORD,
                "restaurant_id": rid,
            },
            201,
        ),
        ("patch", f"/api/v1/users/{target['id']}", {"is_active": False}, 200),
    ]
    staff_ops = [
        ("patch", root + "/accepting-orders", {"is_accepting_orders": True}, 200),
        ("post", root + "/menu/categories", {"name": "Other"}, 201),
        ("patch", root + f"/menu/categories/{cid}", {"position": 2}, 200),
        (
            "post",
            root + "/menu/items",
            {"category_id": cid, "name": "Other", "price_minor": 2000},
            201,
        ),
        ("patch", root + f"/menu/items/{mid}", {"name": "Updated"}, 200),
        ("put", root + f"/menu/items/{mid}/sale-price", {"sale_price_minor": 1000}, 200),
        ("post", root + f"/menu/items/{mid}/archive", None, 200),
    ]
    for operations, allowed in ((admin_ops, "admin"), (staff_ops, "staff_a")):
        for method, path, body, success in operations:
            response = client.request(method, path, headers=h, **({"json": body} if body else {}))
            if role == allowed:
                assert response.status_code == success, (path, response.text)
            else:
                expected = 404 if allowed == "staff_a" and role == "staff_b" else 403
                error(response, expected, "not_found" if expected == 404 else "forbidden")
            unauthenticated = client.request(method, path, **({"json": body} if body else {}))
            error(unauthenticated, 401, "not_authenticated")
    # A fresh menu item keeps the placement check independent of archive success.
    response = place(client, data, customer=role, restaurant=1)
    if role.startswith("customer"):
        ok(response, 201)
    else:
        error(response, 403, "forbidden")
    # The route inventory has no generic update/delete paths around domain rules.
    paths = client.app.openapi()["paths"]
    assert all("delete" not in operations for operations in paths.values())
    assert set(paths["/api/v1/orders/{oid}"]) == {"get"}
    assert set(paths["/api/v1/users/{uid}"]) == {"patch"}


def test_nested_resource_substitution_is_404_and_cannot_mutate_either_menu(client, db_session):
    data = world(client, db_session)
    h = data.headers["staff_a"]
    rid, foreign_rid = data.restaurants
    mid, foreign_mid = data.items
    cid, foreign_cid = data.categories
    root = f"/api/v1/restaurants/{rid}/menu"
    before = [ok(client.get(f"/api/v1/restaurants/{r}/menu")) for r in data.restaurants]
    cases = [
        ("patch", f"{root}/categories/{foreign_cid}", {"name": "Stolen"}),
        (
            "post",
            f"{root}/items",
            {"category_id": foreign_cid, "name": "Foreign", "price_minor": 1000},
        ),
        ("patch", f"{root}/items/{mid}", {"category_id": foreign_cid}),
        ("patch", f"{root}/items/{foreign_mid}", {"name": "Stolen"}),
        ("put", f"{root}/items/{foreign_mid}/sale-price", {"sale_price_minor": 1000}),
        ("post", f"{root}/items/{foreign_mid}/archive", None),
        ("patch", f"/api/v1/restaurants/{foreign_rid}/menu/items/{mid}", {"name": "Stolen"}),
    ]
    for method, path, body in cases:
        error(
            client.request(method, path, headers=h, **({"json": body} if body else {})),
            404,
            "not_found",
        )
    assert [ok(client.get(f"/api/v1/restaurants/{r}/menu")) for r in data.restaurants] == before
    for field in ("role", "restaurant_id", "email"):
        error(
            client.patch("/api/v1/me", headers=data.headers["customer_a"], json={field: "admin"}),
            422,
        )
    error(
        client.patch(
            f"/api/v1/users/{data.ids['staff_a']}",
            headers=data.headers["admin"],
            json={"restaurant_id": foreign_rid},
        ),
        422,
    )
    error(
        client.patch(
            f"/api/v1/users/{data.ids['staff_a']}",
            headers=data.headers["admin"],
            json={"is_active": True},
        ),
        422,
    )


@pytest.mark.parametrize("role", ["customer_a", "staff_a", "admin"])
def test_logout_password_change_and_deactivation_revoke_every_real_token(client, db_session, role):
    data = world(client, db_session)
    email = {
        "customer_a": "customer-a@example.test",
        "staff_a": "staff-a@example.test",
        "admin": "admin@example.test",
    }[role]
    first, second = data.headers[role], auth(client, email)
    wrong = {"current_password": "wrong-password", "new_password": "replacement-passphrase"}
    error(
        client.post("/api/v1/me/change-password", headers=first, json=wrong),
        401,
        "invalid_credentials",
    )
    ok(client.get("/api/v1/me", headers=first))
    assert client.post("/api/v1/me/log-out-everywhere", headers=first).status_code == 204
    for h in (first, second):
        error(client.get("/api/v1/me", headers=h), 401, "not_authenticated")
    fresh, other = auth(client, email), auth(client, email)
    response = client.post(
        "/api/v1/me/change-password", headers=fresh, json=wrong | {"current_password": PASSWORD}
    )
    assert response.status_code == 204 and response.content == b""
    for h in (fresh, other):
        error(client.get("/api/v1/me", headers=h), 401, "not_authenticated")
    error(
        client.post("/api/v1/auth/token", data={"username": email, "password": PASSWORD}),
        401,
        "invalid_credentials",
    )
    token = ok(
        client.post(
            "/api/v1/auth/token", data={"username": email, "password": wrong["new_password"]}
        )
    )["access_token"]
    new_headers = {"Authorization": f"Bearer {token}"}
    ok(client.get("/api/v1/me", headers=new_headers))
    admin_headers = new_headers if role == "admin" else data.headers["admin"]
    account = ok(
        client.patch(
            f"/api/v1/users/{data.ids[role]}", headers=admin_headers, json={"is_active": False}
        )
    )
    assert not account["is_active"]
    error(client.get("/api/v1/me", headers=new_headers), 401, "not_authenticated")
    error(client.get("/api/v1/orders", headers=new_headers), 401, "not_authenticated")
    error(
        client.post(
            "/api/v1/auth/token", data={"username": email, "password": wrong["new_password"]}
        ),
        401,
        "invalid_credentials",
    )


def test_runtime_history_is_append_only(client, db_session):
    data = world(client, db_session)
    receipt = ok(place(client, data), 201)
    oid = UUID(receipt["id"])
    before = list(
        db_session.scalars(select(OrderStatusChange).where(OrderStatusChange.order_id == oid))
    )
    assert len(before) == 1
    for statement in (
        "UPDATE order_status_changes SET reason = 'tampered'",
        "DELETE FROM order_status_changes",
        "TRUNCATE order_status_changes",
    ):
        with pytest.raises(DBAPIError) as caught, db_session.begin_nested():
            db_session.execute(text(statement))
        assert caught.value.orig.sqlstate == "42501"
    assert db_session.scalar(select(func.count()).select_from(OrderStatusChange)) == 1
    assert (
        ok(client.get(f"/api/v1/orders/{oid}", headers=data.headers["customer_a"]))[
            "status_changes"
        ][0]["reason"]
        is None
    )


def test_active_polling_includes_each_active_status_and_cursor_cannot_widen_scope(
    client, db_session
):
    data = world(client, db_session)
    orders = []
    for steps in (
        [],
        ["accepted"],
        ["accepted", "preparing"],
        ["accepted", "preparing", "out_for_delivery"],
        ["accepted", "preparing", "out_for_delivery", "delivered"],
        ["rejected"],
    ):
        order = ok(place(client, data), 201)
        for status in steps:
            ok(
                client.post(
                    f"/api/v1/orders/{order['id']}/status-changes",
                    headers=data.headers["staff_a"],
                    json={"to_status": status, "reason": "Kitchen unavailable"},
                )
            )
        orders.append(order)
    foreign = ok(place(client, data, customer="customer_b", restaurant=1), 201)
    page = ok(client.get("/api/v1/orders?limit=1", headers=data.headers["admin"]))
    cursor = page["next_cursor"]
    for role, expected_ids in (
        ("customer_a", {row["id"] for row in orders}),
        ("staff_a", {row["id"] for row in orders}),
        ("staff_b", {foreign["id"]}),
    ):
        page = ok(
            client.get("/api/v1/orders", headers=data.headers[role], params={"cursor": cursor})
        )
        assert {row["id"] for row in page["items"]} <= expected_ids
        for row in page["items"]:
            assert (
                row["customer_id"] == data.ids["customer_b" if role == "staff_b" else "customer_a"]
            )
    active = ok(client.get("/api/v1/orders?active=true", headers=data.headers["staff_a"]))
    assert {row["status"] for row in active["items"]} == {
        "pending",
        "accepted",
        "preparing",
        "out_for_delivery",
    }
    assert {row["id"] for row in active["items"]} == {row["id"] for row in orders[:4]}


@pytest.mark.concurrency
def test_polling_detail_stays_consistent_when_status_commits_between_its_reads(
    committed_session_factory, database_client, monkeypatch
):
    from app.orders import repository

    with committed_session_factory() as seed, database_client() as setup:
        data = world(setup, seed)
        receipt = ok(place(setup, data), 201)
    url = f"/api/v1/orders/{receipt['id']}"
    with database_client() as poller, database_client() as staff:
        # Warm lazy route schemas outside the controlled database interleaving.
        poller.app.openapi()
        staff.app.openapi()
        original = repository.list_lines
        intervened = False

        def accept_between_reads(session, order_id):
            nonlocal intervened
            if not intervened:
                intervened = True
                ok(
                    staff.post(
                        url + "/status-changes",
                        headers=data.headers["staff_a"],
                        json={"to_status": "accepted"},
                    )
                )
            return original(session, order_id)

        with monkeypatch.context() as patch:
            patch.setattr(repository, "list_lines", accept_between_reads)
            detail = ok(poller.get(url, headers=data.headers["customer_a"]))
        assert intervened
        assert detail["status"] == detail["status_changes"][-1]["to_status"]
        assert detail["status"] == "pending" and len(detail["status_changes"]) == 1
        current = ok(poller.get(url, headers=data.headers["customer_a"]))
        assert current["status"] == "accepted" and len(current["status_changes"]) == 2
