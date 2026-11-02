# 014 — Persist orders, order lines and append-only status changes

Status: complete (new tests deferred at the user's request)

Depends on: [004](004-restaurant-and-customer-storage.md), [009](009-menu-categories-and-items.md), [011](011-order-status-rules.md), [013](013-idempotency-request-contract.md)

Sources: DESIGN §§4, 7.2–7.3, 7.7, 9–10. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add Order/OrderLine/OrderStatusChange models and migration. Use UUID order IDs; BIGINT identity IDs elsewhere; text/check statuses; currency and monetary/address/name snapshots; paid, notes, idempotency key/hash; actor role/user, reason and UTC database timestamps.

Standardise the FK name to menu_item_id as used by the API/design prose; record the ER diagram's item_id spelling discrepancy. Add all §4 indexes, including unique customer/key and partial active-order index. Enforce line arithmetic/quantity/prices and total arithmetic; sum-of-lines validation remains in the service.

Use the non-owner runtime role from task 3. Grant it only SELECT/INSERT on order_status_changes and the sequence privileges needed to insert; explicitly deny UPDATE/DELETE/TRUNCATE and schema ownership. Migrations/privileged test cleanup use different credentials. Keep runtime grants reproducible for fresh installs.

Provide own-table insert/read helpers with flush but no commits. Snapshots have no update API.

## Acceptance and verification

Upgrade empty and preceding schemas, run alembic check, and test unique customer/key, all checks/FKs, timestamp defaults and indexes. Using the real runtime credentials, insert/read history successfully and prove UPDATE, DELETE and TRUNCATE fail. Use privileged fixture cleanup so tests do not require weakening runtime permissions.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Added order/line/history models, own-table repository helpers and explicit migration 0004. Storage includes UUID orders, identity lines/history, immutable currency/address/name/price snapshots, customer/key uniqueness and request hash, all required FKs/checks/indexes and DB UTC timestamps. Standardized menu_item_id from the ER diagram's item_id spelling. Initial history is constrained to customer/null→pending/no reason with one initial event per order. Refund owed is derived, not stored.

Migration revokes broad/public access, grants runtime SELECT/INSERT and sequence use, and permits UPDATE only for orders.status/updated_at. History and line snapshots cannot be updated/deleted/truncated by runtime; snapshot columns on orders cannot be updated. Repositories never commit. No routes/test files were added.

Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, with migration upgrade/check and no drift.
- Ephemeral owner transaction: downgrade to 0003 → upgrade head/check, then downgrade base → upgrade head/check, both passed; transaction rolled back to preserve the original schema.
- `PYTHONPATH="$PWD:/tmp" .venv/bin/python /tmp/takeaway_smoke_014.py`: passed runtime inserts/reads/defaults, customer/key uniqueness, arithmetic/bounds/shape/FK rejection, required indexes, derived refund and actual permission-denied UPDATE/DELETE/TRUNCATE attempts against history/snapshots. All data rolled back.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed. No automated tests added or modified.
