"""HTTP transition rules, error precedence, rollback and stable creation replay."""

from uuid import uuid4

import pytest

from app.orders import repository
from tests.order_support import ok, place, world

pytestmark = pytest.mark.integration
# Independent contract paths cover every allowed transition and terminal status.
PATHS = [
    [("customer_a", "cancelled", None)],
    [("staff_a", "rejected", "  Kitchen unavailable  ")],
    [("staff_a", "accepted", None), ("staff_a", "cancelled", "  Closed  ")],
    [
        ("staff_a", "accepted", None),
        ("staff_a", "preparing", None),
        ("staff_a", "cancelled", "  Equipment failure  "),
    ],
    [
        ("staff_a", "accepted", "  OK  "),
        ("staff_a", "preparing", None),
        ("staff_a", "out_for_delivery", None),
        ("staff_a", "delivered", None),
    ],
]
ALLOWED = {
    "pending": {"accepted": "staff_a", "rejected": "staff_a", "cancelled": "customer_a"},
    "accepted": {"preparing": "staff_a", "cancelled": "staff_a"},
    "preparing": {"out_for_delivery": "staff_a", "cancelled": "staff_a"},
    "out_for_delivery": {"delivered": "staff_a"},
}
STATUSES = {
    "pending",
    "accepted",
    "preparing",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "rejected",
}


@pytest.mark.parametrize("path", PATHS)
def test_status_rules_history_refunds_and_stable_replay(client, db_session, path):
    data = world(client, db_session)
    key = uuid4()
    receipt = ok(place(client, data, key=key), 201)
    url = f"/api/v1/orders/{receipt['id']}"
    before = ok(client.get(url, headers=data.headers["customer_a"]))
    for actor, target, reason in path + [(None, None, None)]:
        source = before["status"]
        for candidate in STATUSES:
            for role in ("customer_a", "staff_a"):
                if candidate not in ALLOWED.get(source, {}):
                    expected, code = 409, "invalid_transition"
                elif ALLOWED[source][candidate] != role:
                    expected, code = 403, "transition_not_permitted"
                elif candidate == "rejected" or (candidate == "cancelled" and role == "staff_a"):
                    expected, code = 422, "reason_required"
                else:
                    continue
                response = client.post(
                    url + "/status-changes",
                    headers=data.headers[role],
                    json={"to_status": candidate, "reason": "  "},
                )
                assert response.status_code == expected, response.text
                assert response.json()["code"] == code
        assert ok(client.get(url, headers=data.headers["customer_a"])) == before
        if actor is None:
            break
        after = ok(
            client.post(
                url + "/status-changes",
                headers=data.headers[actor],
                json={"to_status": target, "reason": reason},
            )
        )
        assert after["status"] == target
        assert after["refund_owed"] == (target in {"cancelled", "rejected"})
        assert after["status_changes"][:-1] == before["status_changes"]
        last = after["status_changes"][-1]
        assert last["from_status"] == source and last["to_status"] == target
        assert last["actor_user_id"] == data.ids[actor]
        assert last["actor_role"] == actor.split("_")[0]
        assert last["reason"] == (reason.strip() if reason else None)
        assert last["created_at"].endswith("Z") and after["updated_at"].endswith("Z")
        before = after
    replay = place(client, data, key=key)
    assert ok(replay, 201) == receipt and replay.headers["Idempotent-Replayed"] == "true"
    active = ok(client.get("/api/v1/orders?active=true", headers=data.headers["staff_a"]))
    assert active == {"items": []}


def test_scope_precedes_rules_and_history_failure_rolls_back_everything(
    client, db_session, monkeypatch
):
    data = world(client, db_session)
    receipt = ok(place(client, data), 201)
    url = f"/api/v1/orders/{receipt['id']}"
    before = ok(client.get(url, headers=data.headers["customer_a"]))
    for role in ("customer_b", "staff_b", "admin"):
        response = client.post(
            url + "/status-changes", headers=data.headers[role], json={"to_status": "pending"}
        )
        assert response.status_code == (403 if role == "admin" else 404)
        assert response.json()["code"] == ("forbidden" if role == "admin" else "not_found")
    assert client.post(url + "/status-changes", json={"to_status": "accepted"}).status_code == 401
    for body in (
        {"to_status": "unknown"},
        {"to_status": "accepted", "actor_user_id": 1},
        {"to_status": "accepted", "reason": 1},
        {"to_status": "accepted", "reason": "x" * 1001},
    ):
        assert (
            client.post(
                url + "/status-changes", headers=data.headers["staff_a"], json=body
            ).status_code
            == 422
        )
    original = repository.append_status_change

    def fail_after_insert(session, change):
        original(session, change)
        raise RuntimeError("injected history failure")

    monkeypatch.setattr(repository, "append_status_change", fail_after_insert)
    with pytest.raises(RuntimeError, match="injected history failure"):
        client.post(
            url + "/status-changes", headers=data.headers["staff_a"], json={"to_status": "accepted"}
        )
    assert ok(client.get(url, headers=data.headers["customer_a"])) == before
