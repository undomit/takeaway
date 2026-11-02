# 017 — Implement scoped order detail, history and polling lists

Status: complete

Depends on: [016](016-place-orders-atomically.md)

Sources: DESIGN §§4–5, 7.6, 7.8–7.9, 8; ADRs 0001–0002. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement the single orders.repository.visible_to(user) entry point for every order read: customer_id for customers, restaurant_id for staff, no restriction for admins. GET /orders/{oid} includes current status, immutable snapshots, ordered status history and derived refund owed.

Implement GET /orders history with created_at/id keyset pagination and task 1 ordering/limit/cursor rules. Apply scope before filtering/pagination.

Implement staff GET /orders?active=true returning the complete list across pending/accepted/preparing/out_for_delivery, without pagination or updated_since. Specify/reject active=true for nonstaff according to task 1.

Document customer/staff polling every ~10 seconds, customers stopping at terminal status. Never expose another customer's or restaurant's address through detail, lines or history.

## Acceptance and verification

Parametrise detail/list across customer A/B, staff X/Y and admin with seeded orders. Confirm 404 outside scope, all admin reads, correct line/history serialization and no duplicate/missing history pages with equal timestamps. Seed more than 50 active orders to prove the kitchen list is complete; terminal orders are excluded. Repeat GETs and verify zero writes.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Verification

`uv run --locked pytest -W error` — 51 passed. `uv run --locked ruff check .`, `uv run --locked ruff format --check .` and `uv run --locked lint-imports` passed. The PostgreSQL fixture upgrades and checks Alembic with the owner and runs requests with restricted runtime credentials. Two focused scenarios cover scoped detail/history, equal-timestamp pagination, strict queries, 53 active orders and read-only polling.
