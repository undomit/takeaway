# 004 — Persist restaurants and account identities

Status: planned

Depends on: [003](003-postgres-and-test-harness.md)

Sources: DESIGN §4, §§7.4, 8; ADRs 0001, 0003. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add Restaurant and User models/repositories plus a migration. Include saved-address fields, role, restaurant_id, token_version, is_active, password_hash and all designed timestamps. Use BIGINT identity IDs, BIGINT money, text/check roles, database-generated UTC timestamptz values and database now() on restaurant updates.

Enforce staff/exactly-one-restaurant equivalence, customer-only saved-address fields, unique lower(email), unique restaurant slug and money bounds from task 1. Preserve foreign keys with restrictive deletion behaviour. Repository methods query only their module tables.

Expose users.service lookup functions for auth so token dependencies do not query users repositories directly. Internal lookup services must not commit.

## Acceptance and verification

Test round-trip persistence and PostgreSQL rejection of mixed-case duplicate email, invalid roles, staff without a restaurant, customer/admin with a restaurant, saved-address fields on staff/admin and negative delivery fees. Verify database timestamps are timezone aware. Upgrade from task 3 and run alembic check.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
