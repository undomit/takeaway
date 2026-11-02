# 004 — Persist restaurants and account identities

Status: complete

Depends on: [003](003-postgres-and-test-harness.md)

Sources: DESIGN §4, §§7.4, 8; ADRs 0001, 0003. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add Restaurant and User models/repositories plus a migration. Include saved-address fields, role, restaurant_id, token_version, is_active, password_hash and all designed timestamps. Use BIGINT identity IDs, BIGINT money, text/check roles, database-generated UTC timestamptz values and database now() on restaurant updates.

Enforce staff/exactly-one-restaurant equivalence, customer-only saved-address fields, unique lower(email), unique restaurant slug and money bounds from task 1. Preserve foreign keys with restrictive deletion behaviour. Repository methods query only their module tables.

Expose users.service lookup functions for auth so token dependencies do not query users repositories directly. Internal lookup services must not commit.

## Acceptance and verification

Test round-trip persistence and PostgreSQL rejection of mixed-case duplicate email, invalid roles, staff without a restaurant, customer/admin with a restaurant, saved-address fields on staff/admin and negative delivery fees. Verify database timestamps are timezone aware. Upgrade from task 3 and run alembic check.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Completion evidence — 2026-11-02

Added Restaurant and User models, own-table repositories and read-only users.service lookups for authentication. Models use BIGINT GENERATED ALWAYS AS IDENTITY IDs, BIGINT money, TEXT/check roles with a Python Role enum, database-generated UTC timestamps and SQL `now()` on restaurant updates. Registered both models in the Alembic/application metadata registry.

Revision 0002 adds case-insensitive unique email, unique restaurant slug, staff/exactly-one-restaurant and role constraints, all-field customer-only saved addresses, complete-or-absent saved-address shape, nonnegative token versions, safe JSON delivery-fee bounds and restrictive restaurant references. Runtime receives SELECT/INSERT/UPDATE and sequence access, with no DELETE/TRUNCATE or migration-table grants. MIGRATION_RUNTIME_ROLE selects an existing login (development default, separate test override); migration-owner credentials stay separate.

Added only two integration scenarios: persisted onboarding/account changes and lookups, and database rejection of invalid identity/restaurant/address/fee combinations. They exercise independent committed sessions, case-insensitive lookup, role enum/default round-trips, zero delivery fee, UTC/database timestamps, read services not committing caller changes, restrictive restaurant deletion, and every required integrity boundary. Registration, password hashing, login and HTTP endpoints remain in later tasks.

Verification passed on Python 3.12.16 and PostgreSQL 16.15:

- `.venv/bin/pytest tests/integration/test_account_storage.py -q -W error --tb=short`: **2 passed**; setup upgraded the preserved task 003 database from revision 0001 to 0002 and checked metadata agreement.
- `.venv/bin/pytest -q -W error --tb=short`: **45 passed** (43 existing plus two new scenarios).
- With dedicated test owner credentials and MIGRATION_RUNTIME_ROLE=takeaway_test_runtime, `.venv/bin/alembic upgrade head` passed and `.venv/bin/alembic check` reported no new upgrade operations.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` and `.venv/bin/lint-imports`: passed; all three architecture contracts kept.
- `uv lock --check --offline` and `git diff --check`: passed; no dependency changes required.

See [README.md](../README.md) for schema, privileges and role configuration. The test database remains separate from development; no real customer data is used.
