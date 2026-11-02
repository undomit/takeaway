# 012 — Implement pure order pricing and snapshots

Status: complete (new tests deferred at the user's request)

Depends on: [010](010-sale-prices.md), [011](011-order-status-rules.md)

Sources: DESIGN §§1 A4–A5, 4, 7.2, 7.4, 7.10, 10; ADR 0003. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement pure pricing over snapshot-ready menu values, quantities, delivery fee and currency. Return order lines with menu_item_id, item_name, charged unit price, original unit price, quantity and line total, plus subtotal/fee/total.

Reject empty lines, duplicates, quantities outside 1–20 and noninteger quantities/money according to task 1. Use fixed sale price when present; no order-time percentage calculations.

Ensure values fit PostgreSQL BIGINT at all multiplication/sum boundaries and return validation errors instead of database overflow. Do not trust or accept client prices. Keep all results integer minor units.

## Acceptance and verification

Unit-test normal/sale/mixed orders, repeated quantities, zero fee, empty input, duplicate menu items, quantities 0/21, boolean/fractional values, arithmetic limits and overflow. Assert exact values and type(value) is int for every monetary result. No database access is needed.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Implemented pure price_order over a structural server-menu interface and separately validated ID/quantity selections. Shared strict values reject boolean/float/string quantities and money, empty/duplicate/excessive lines and invalid prices/currency. Frozen line/order results copy item names, original normal prices, charged fixed-sale prices and quantities. Line multiplication, subtotal summation and total-plus-fee results are each bounded by the API safe integer maximum. No percentage work, database imports or HTTP imports occur in pricing. Errors are Pydantic validation errors for the future transport layer to map; no order endpoint is exposed.

No routes, schema migrations or tests were added. Verification:

- `.venv/bin/python /tmp/takeaway_smoke_012.py`: passed mixed normal/sale pricing, copied/immutable values, integer result types, zero fees, supported maxima, original-price preservation, invalid types/quantities/prices, empty/duplicate/excessive lines, missing menu snapshots, and separate line/subtotal/total overflow boundaries; imports included neither SQLAlchemy nor FastAPI.
- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, including PostgreSQL migration upgrade/check.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed.
