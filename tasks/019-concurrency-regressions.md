# 019 — Verify concurrent checkout and status changes

Status: complete

Depends on: [018](018-change-order-status.md)

Sources: DESIGN §§7.3, 7.5, 10. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add concurrency tests with separate connections/sessions and real commits; coordinate with barriers at the read/insert/update points rather than relying on sleeps. Use isolated seeded data and privileged cleanup; never reuse the savepoint fixture across threads.

Race customer cancellation against staff acceptance after both read pending. Race identical order placements with the same customer/key and then different bodies sharing a key. Verify two different customers can independently use the same UUID key.

If failures reveal bugs, fix their owning services in this task without changing the contract. Keep timeouts bounded and include useful thread/error diagnostics.

## Acceptance and verification

For cancel/accept, exactly one succeeds and one returns 409 status_conflict; history has exactly two rows including placement. Identical checkout requests both return 201 with identical receipts, exactly one order/line set/initial history exists and only one gateway call occurs. Mismatched bodies produce one winner and one 422, never a generic 500. Tests pass against PostgreSQL with the restricted runtime role and leave no committed fixture data.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Verification

`uv run --locked pytest tests/integration/test_order_concurrency.py -q -W error` — 4 passed. `uv run --locked pytest -W error -q` — 61 passed. Ruff lint/format and all three import-linter contracts passed.

The four scenarios race identical placements, mismatched bodies, independent customers sharing one UUID, and pending cancellation versus acceptance. Barriers run immediately before insert or after both scoped reads; PostgreSQL backend IDs prove independent connections. Each request uses real login and runtime-role commits; assertions cover receipt equality, replay header, exact order/line/event counts, gateway calls and matching winner history. Statement/lock/barrier/future timeouts bound failure, with both worker errors reported. Existing privileged fixture cleanup removes committed data before/after each case. Apps and their lazy schemas initialize sequentially before request workers start, avoiding a FastAPI/Pydantic first-use schema-construction warning under `-W error`. No production fix was needed.
