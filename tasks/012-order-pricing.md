# 012 — Implement pure order pricing and snapshots

Status: planned

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
