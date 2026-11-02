"""Complete release acceptance through Compose HTTPS in a fresh disposable stack."""

import argparse
import json
import re
import tempfile
import time
from urllib.parse import urlencode
from uuid import uuid4

from proxy_smoke import Proxy
from runtime_smoke import ROOT, Stack

PASSWORD = "release-smoke-passphrase"


class Flow:
    def __init__(self, proxy):
        self.proxy = proxy
        self.last_order_post = 0.0

    def request(self, path, *, expected=200, method="GET", headers=None, body=None):
        # Exercise the real production limiter without allowing smoke traffic to exceed it.
        if path == "/api/v1/orders" and method == "POST":
            time.sleep(max(0, 6.2 - (time.monotonic() - self.last_order_post)))
            self.last_order_post = time.monotonic()
        status, response_headers, response = self.proxy.request(
            path, method=method, headers=headers, body=body
        )
        # Never print response bodies: a failed assertion must not expose login tokens.
        assert status == expected, f"{method} {path}: expected {expected}, got {status}"
        return (json.loads(response) if response else None), response_headers

    def call(self, path, **kwargs):
        return self.request(path, **kwargs)[0]

    def login(self, email, password=PASSWORD):
        token = self.call(
            "/api/v1/auth/token",
            method="POST",
            body=urlencode({"username": email, "password": password}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )["access_token"]
        return {"Authorization": "Bearer " + token}

    def register(self, email):
        return self.call(
            "/api/v1/auth/register",
            method="POST",
            expected=201,
            body={"email": email, "full_name": "Release Customer", "password": PASSWORD},
        )


def verify_routes(flow):
    """Read the source contract, so newly documented routes cannot silently disappear."""
    document = (ROOT / "docs/api-contract.md").read_text()
    matrix = document.split("## Route and permission matrix", 1)[1].split(
        "## Account operations", 1
    )[0]
    expected = {}
    for row in matrix.splitlines():
        match = re.match(r"\| (GET|POST|PATCH|PUT) \| `([^`]+)`.*", row)
        if not match:
            continue
        method, path = match.groups()
        path = path.split("?", 1)[0]
        if path not in {"/healthz", "/readyz"}:
            path = "/api/v1" + path
        fields = row.split("|")
        public = fields[3].strip().startswith("Public")
        expected[(path, method.lower())] = (public, fields[5].strip().split()[0])
    spec = flow.call("/openapi.json")
    actual = {
        (path, method): operation
        for path, methods in spec["paths"].items()
        for method, operation in methods.items()
        if method in {"get", "post", "patch", "put", "delete", "options", "head"}
    }
    assert actual.keys() == expected.keys(), "Live OpenAPI differs from task 001 route matrix"
    for (path, method), (public, success) in expected.items():
        operation = actual[(path, method)]
        assert bool(operation.get("security")) == (not public), (method, path, "security")
        assert success in operation["responses"], (method, path, "success status")
        if not public:
            concrete = re.sub(r"\{\w+\}", "1", path)
            concrete = concrete.replace("/orders/1", "/orders/" + str(uuid4()))
            flow.call(
                concrete,
                method=method.upper(),
                expected=401,
                body={} if method in {"post", "patch", "put"} else None,
                headers={"Idempotency-Key": str(uuid4())},
            )
    print(
        f"PASS: all {len(expected)} contract operations match live OpenAPI/authentication",
        flush=True,
    )


def verify(flow, stack):
    assert flow.call("/healthz") == {"status": "ok"}
    assert flow.call("/readyz") == {"status": "ready"}
    # Drive the actual CLI; supply getpass input inside this disposable container only.
    stack.python(
        "from unittest.mock import patch; from app.cli import main; "
        f"p=patch('app.cli.getpass.getpass',return_value={PASSWORD!r}); p.start(); "
        "raise SystemExit(main(['create-admin','--email','admin@example.test',"
        "'--full-name','Release Admin']))"
    )
    admin = flow.login("admin@example.test")
    rid = flow.call(
        "/api/v1/restaurants",
        method="POST",
        expected=201,
        headers=admin,
        body={"name": "Release Kitchen", "slug": "release-kitchen", "delivery_fee_minor": 100},
    )["id"]
    root = f"/api/v1/restaurants/{rid}"
    flow.call(root, method="PATCH", headers=admin, body={"delivery_fee_minor": 250})
    staff_account = flow.call(
        "/api/v1/users",
        method="POST",
        expected=201,
        headers=admin,
        body={
            "email": "staff@example.test",
            "full_name": "Release Staff",
            "password": PASSWORD,
            "restaurant_id": rid,
        },
    )
    staff = flow.login("staff@example.test")
    customer_account = flow.register("customer@example.test")
    customer = flow.login("customer@example.test")
    flow.register("other@example.test")
    other = flow.login("other@example.test")
    address = {"address_line1": "Original Street", "postcode": "AB1", "phone": "+441234"}
    flow.call("/api/v1/me", method="PATCH", headers=customer, body={"saved_address": address})
    category = flow.call(
        root + "/menu/categories",
        method="POST",
        expected=201,
        headers=staff,
        body={"name": "Mains"},
    )
    flow.call(
        root + f"/menu/categories/{category['id']}",
        method="PATCH",
        headers=staff,
        body={"name": "Main courses", "position": 1},
    )
    item = flow.call(
        root + "/menu/items",
        method="POST",
        expected=201,
        headers=staff,
        body={"category_id": category["id"], "name": "Original Soup", "price_minor": 1250},
    )
    item_path = root + f"/menu/items/{item['id']}"
    sale = flow.call(
        item_path + "/sale-price", method="PUT", headers=staff, body={"percentage_off": "15.00"}
    )
    assert sale["sale_price_minor"] == 1063
    flow.call(
        root + "/accepting-orders",
        method="PATCH",
        headers=staff,
        body={"is_accepting_orders": True},
    )
    assert flow.call(root)["is_accepting_orders"]
    assert flow.call(root + "/menu")["categories"][0]["items"][0]["id"] == item["id"]
    assert flow.call("/api/v1/restaurants")["items"][0]["id"] == rid
    intent = {"restaurant_id": rid, "lines": [{"menu_item_id": item["id"], "quantity": 2}]}
    key = {"Idempotency-Key": str(uuid4())}
    receipt, first_headers = flow.request(
        "/api/v1/orders",
        method="POST",
        expected=201,
        headers=customer | key,
        body=intent,
    )
    assert first_headers.get("Idempotent-Replayed") is None
    assert receipt["total_minor"] == 2376 and receipt["currency"] == "EUR" and receipt["paid"]
    order_path = "/api/v1/orders/" + receipt["id"]
    active = flow.call("/api/v1/orders?active=true", headers=staff)["items"]
    assert [row["id"] for row in active] == [receipt["id"]]
    assert flow.call("/api/v1/orders", headers=customer)["items"][0]["id"] == receipt["id"]
    for index, target in enumerate(("accepted", "preparing", "out_for_delivery", "delivered"), 2):
        detail = flow.call(
            order_path + "/status-changes", method="POST", headers=staff, body={"to_status": target}
        )
        assert detail["status"] == target and len(detail["status_changes"]) == index
        assert flow.call(order_path, headers=customer) == detail
    assert flow.call("/api/v1/orders?active=true", headers=staff)["items"] == []
    assert not detail["refund_owed"]
    flow.call(
        item_path,
        method="PATCH",
        headers=staff,
        body={"name": "Changed Soup", "price_minor": 2000, "sale_price_minor": None},
    )
    flow.call(root, method="PATCH", headers=admin, body={"delivery_fee_minor": 500})
    flow.call(
        "/api/v1/me",
        method="PATCH",
        headers=customer,
        body={"saved_address": address | {"address_line1": "Changed Street"}},
    )
    replay, replay_headers = flow.request(
        "/api/v1/orders",
        method="POST",
        expected=201,
        headers=customer | key,
        body=intent,
    )
    assert replay == receipt and replay_headers["Idempotent-Replayed"] == "true"
    current = flow.call(order_path, headers=customer)
    for field in (
        "lines",
        "delivery_address",
        "subtotal_minor",
        "delivery_fee_minor",
        "total_minor",
    ):
        assert current[field] == receipt[field], field
    assert current["status"] == "delivered" and receipt["status"] == "pending"
    flow.call(order_path, headers=other, expected=404)
    flow.call(
        order_path + "/status-changes",
        method="POST",
        headers=admin,
        expected=403,
        body={"to_status": "cancelled", "reason": "Not permitted"},
    )
    flow.call(item_path, method="PATCH", headers=customer, expected=403, body={"name": "No"})
    foreign_rid = flow.call(
        "/api/v1/restaurants",
        method="POST",
        expected=201,
        headers=admin,
        body={"name": "Other Kitchen", "slug": "other-kitchen", "delivery_fee_minor": 0},
    )["id"]
    flow.call(
        f"/api/v1/restaurants/{foreign_rid}/accepting-orders",
        method="PATCH",
        headers=staff,
        expected=404,
        body={"is_accepting_orders": True},
    )
    print(
        "PASS: onboarding, pricing, saved address, fulfilment/polling, "
        "immutable replay/snapshots and scope",
        flush=True,
    )
    for target, actor in (("rejected", staff), ("cancelled", customer)):
        placed = flow.call(
            "/api/v1/orders",
            method="POST",
            expected=201,
            headers=customer | {"Idempotency-Key": str(uuid4())},
            body=intent,
        )
        terminal = flow.call(
            f"/api/v1/orders/{placed['id']}/status-changes",
            method="POST",
            headers=actor,
            body={"to_status": target, "reason": "Release acceptance"},
        )
        assert terminal["status"] == target and terminal["paid"] and terminal["refund_owed"]
        assert len(terminal["status_changes"]) == 2
    archived = flow.call(item_path + "/archive", method="POST", headers=staff)
    assert archived["is_archived"]
    print(
        "PASS: paid rejection/cancellation derive refund owed; no real refund; item archived",
        flush=True,
    )
    flow.call(
        "/api/v1/me/change-password",
        method="POST",
        expected=204,
        headers=customer,
        body={"current_password": PASSWORD, "new_password": PASSWORD + "-new"},
    )
    flow.call("/api/v1/me", headers=customer, expected=401)
    customer = flow.login("customer@example.test", PASSWORD + "-new")
    flow.call("/api/v1/me/log-out-everywhere", method="POST", expected=204, headers=customer)
    flow.call("/api/v1/me", headers=customer, expected=401)
    customer = flow.login("customer@example.test", PASSWORD + "-new")
    for account, headers in ((customer_account, customer), (staff_account, staff)):
        deactivated = flow.call(
            f"/api/v1/users/{account['id']}",
            method="PATCH",
            headers=admin,
            body={"is_active": False},
        )
        assert not deactivated["is_active"]
        flow.call("/api/v1/me", headers=headers, expected=401)
    assert flow.call(order_path, headers=admin)["status"] == "delivered"
    verify_routes(flow)
    assert flow.call("/readyz") == {"status": "ready"}
    print("PASS: password change, logout, deactivation and health/readiness", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="takeaway-app:local")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="takeaway-release-") as directory:
        stack = Stack(directory, args.image)
        try:
            verify(Flow(Proxy(stack)), stack)
        except Exception:
            # Request logs contain correlation/status only, never credentials or bodies.
            print(stack.compose("logs", "--no-log-prefix", "nginx", "app", check=False).stdout)
            raise
        finally:
            stack.cleanup()


if __name__ == "__main__":
    main()
