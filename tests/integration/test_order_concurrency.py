"""Deterministic races with independent runtime connections and real commits."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Barrier, Lock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.orders import repository
from app.orders.models import Order, OrderLine, OrderStatusChange
from app.payments.dependencies import get_payment_gateway
from app.payments.gateway import PaymentOutcome, PaymentResult
from tests.order_support import ok, place, world

pytestmark = [pytest.mark.integration, pytest.mark.concurrency]


class CountingGateway:
    def __init__(self):
        self.calls = []
        self.lock = Lock()

    def create_payment(self, order_id, amount_minor, currency, idempotency_key):
        with self.lock:
            self.calls.append((order_id, amount_minor, currency, idempotency_key))
        return PaymentResult(PaymentOutcome.PAID)


def run_pair(database_client, gateway, calls):
    """Each worker owns its app, Session, connection and cleanup lifecycle."""

    def worker(client, call):
        response = call(client)
        assert client.app.state.database.engine.pool.checkedout() == 0
        return response

    # Build each app's lazy schema sequentially before racing requests. Concurrent
    # Pydantic/FastAPI schema construction is outside the database behavior tested.
    with ExitStack() as stack:
        clients = [stack.enter_context(database_client()) for _ in calls]
        for client in clients:
            client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
            client.app.openapi()
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="order-race") as pool:
            futures = [
                pool.submit(worker, client, call)
                for client, call in zip(clients, calls, strict=True)
            ]
            # SQL statement/lock timeouts and barrier timeouts bound worker cleanup too.
            results, failures = [], []
            for future in futures:
                try:
                    results.append(future.result(timeout=20))
                except Exception as exc:
                    failures.append(repr(exc))
            assert not failures, f"Race workers failed: {failures}"
            return results


def rendezvous(session, barrier, pids):
    session.execute(text("SET LOCAL statement_timeout = '8s'"))
    session.execute(text("SET LOCAL lock_timeout = '8s'"))
    pids.add(session.scalar(text("SELECT pg_backend_pid()")))
    barrier.wait(timeout=8)


@pytest.mark.parametrize("mode", ["identical", "different_body", "different_customer"])
def test_checkout_races_have_one_payment_per_winner_and_customer_scoped_keys(
    committed_session_factory, database_client, monkeypatch, mode
):
    with committed_session_factory() as seed, database_client() as setup:
        data = world(setup, seed)
    barrier, pids, gateway, key = Barrier(2), set(), CountingGateway(), uuid4()
    original = repository.add_order

    def synchronized_insert(session, order):
        rendezvous(session, barrier, pids)
        return original(session, order)

    monkeypatch.setattr(repository, "add_order", synchronized_insert)
    other_customer = "customer_b" if mode == "different_customer" else "customer_a"
    quantity = 3 if mode == "different_body" else 2
    responses = run_pair(
        database_client,
        gateway,
        [
            lambda client: place(client, data, key=key),
            lambda client: place(
                client,
                data,
                key=key,
                customer=other_customer,
                lines=[{"menu_item_id": data.items[0], "quantity": quantity}],
            ),
        ],
    )
    assert len(pids) == 2, f"Race must use separate PostgreSQL connections: {pids}"
    assert sorted(response.status_code for response in responses) == (
        [201, 422] if mode == "different_body" else [201, 201]
    ), [(response.status_code, response.text) for response in responses]
    if mode == "identical":
        assert responses[0].json() == responses[1].json()
        assert sorted(
            response.headers.get("Idempotent-Replayed", "false") for response in responses
        ) == ["false", "true"]
    if mode == "different_body":
        loser = next(response for response in responses if response.status_code == 422)
        assert loser.json()["code"] == "idempotency_key_reused"
    winners = 2 if mode == "different_customer" else 1
    assert len(gateway.calls) == winners
    with committed_session_factory() as observer:
        for model in (Order, OrderLine, OrderStatusChange):
            assert observer.scalar(select(func.count()).select_from(model)) == winners
        rows = list(observer.scalars(select(Order)))
        assert {row.id for row in rows} == {call[0] for call in gateway.calls}
        assert all(row.idempotency_key == key and row.paid for row in rows)
        assert {row.customer_id for row in rows} == (
            {data.ids["customer_a"], data.ids["customer_b"]}
            if winners == 2
            else {data.ids["customer_a"]}
        )


def test_pending_accept_cancel_race_commits_one_matching_history_entry(
    committed_session_factory, database_client, monkeypatch
):
    with committed_session_factory() as seed, database_client() as setup:
        data = world(setup, seed)
        receipt = ok(place(setup, data), 201)
    barrier, pids, gateway = Barrier(2), set(), CountingGateway()
    original = repository.get_visible

    def synchronized_read(session, user, order_id):
        order = original(session, user, order_id)
        assert order.status == "pending"
        rendezvous(session, barrier, pids)
        return order

    monkeypatch.setattr(repository, "get_visible", synchronized_read)
    url = f"/api/v1/orders/{receipt['id']}/status-changes"
    responses = run_pair(
        database_client,
        gateway,
        [
            lambda client: client.post(
                url, headers=data.headers["customer_a"], json={"to_status": "cancelled"}
            ),
            lambda client: client.post(
                url, headers=data.headers["staff_a"], json={"to_status": "accepted"}
            ),
        ],
    )
    assert len(pids) == 2
    assert sorted(response.status_code for response in responses) == [200, 409], [
        (response.status_code, response.text) for response in responses
    ]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["code"] == "status_conflict"
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert len(winner["status_changes"]) == 2
    assert gateway.calls == []
    with committed_session_factory() as observer:
        order = observer.get(Order, UUID(receipt["id"]))
        changes = repository.list_status_changes(observer, order.id)
        assert len(changes) == 2
        assert changes[-1].from_status == "pending"
        assert changes[-1].to_status == order.status == winner["status"]
        role = "staff_a" if order.status == "accepted" else "customer_a"
        assert changes[-1].actor_user_id == data.ids[role]
        assert order.updated_at == changes[-1].created_at
