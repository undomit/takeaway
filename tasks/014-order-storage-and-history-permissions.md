# 014 — Persist orders, order lines and append-only status changes

Status: planned

Depends on: [004](004-restaurant-and-customer-storage.md), [009](009-menu-categories-and-items.md), [011](011-order-status-rules.md), [013](013-idempotency-request-contract.md)

Sources: DESIGN §§4, 7.2–7.3, 7.7, 9–10. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add Order/OrderLine/OrderStatusChange models and migration. Use UUID order IDs; BIGINT identity IDs elsewhere; text/check statuses; currency and monetary/address/name snapshots; paid, notes, idempotency key/hash; actor role/user, reason and UTC database timestamps.

Standardise the FK name to menu_item_id as used by the API/design prose; record the ER diagram's item_id spelling discrepancy. Add all §4 indexes, including unique customer/key and partial active-order index. Enforce line arithmetic/quantity/prices and total arithmetic; sum-of-lines validation remains in the service.

Use the non-owner runtime role from task 3. Grant it only SELECT/INSERT on order_status_changes and the sequence privileges needed to insert; explicitly deny UPDATE/DELETE/TRUNCATE and schema ownership. Migrations/privileged test cleanup use different credentials. Keep runtime grants reproducible for fresh installs.

Provide own-table insert/read helpers with flush but no commits. Snapshots have no update API.

## Acceptance and verification

Upgrade empty and preceding schemas, run alembic check, and test unique customer/key, all checks/FKs, timestamp defaults and indexes. Using the real runtime credentials, insert/read history successfully and prove UPDATE, DELETE and TRUNCATE fail. Use privileged fixture cleanup so tests do not require weakening runtime permissions.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
