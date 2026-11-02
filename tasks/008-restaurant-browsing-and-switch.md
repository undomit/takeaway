# 008 — Expose restaurant browsing and accepting-orders control

Status: complete (new tests deferred at the user's request)

Depends on: [007](007-admin-onboarding.md)

Sources: DESIGN §§1 A7, 5, 7.11, 8; ADR 0001. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add public restaurant list/detail with delivery fee and accepting-orders flag. Use the task 1 keyset contract with stable created_at/id ordering for lists.

Add the staff-only accepting-orders operation, restricted to the caller's own restaurant. Out-of-scope staff get 404; other roles get 403. Update timestamps in PostgreSQL.

Expose restaurants.service.get_for_ordering using the caller's session, returning an immutable ordering view and enforcing accepting orders. It must not lock restaurant rows or commit when called from an order use case.

## Acceptance and verification

Test public list/detail, deterministic pagination including equal timestamps, missing resources and invalid cursors. Test switch on/off and the role/scope matrix for two restaurants. Verify get_for_ordering rejects nonaccepting restaurants with restaurant_not_accepting_orders and does not commit its caller's work.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Added public restaurant list/detail, strict keyset cursors and staff-owned accepting-orders writes. Pagination fetches one extra row and orders descending by creation timestamp and ID; malformed/noncanonical base64url, duplicate/unexpected cursor members, wrong resources/versions/types and invalid timestamps are rejected. Switch writes enforce role then own-restaurant scope, strict booleans and database timestamps. Immutable get_for_ordering reads reject missing/nonaccepting restaurants without locking or committing. Menu routes mount before the general restaurant-ID route to avoid shadowing.

No schema change was needed. No test files were added or modified, per the user's instruction. Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, including fixture-managed PostgreSQL Alembic upgrade/check. An initial router-mount regression was fixed by ordering the specific menu router before the general restaurant router.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed.
- `PYTHONPATH="$PWD:/tmp" .venv/bin/python /tmp/takeaway_smoke_008.py`: passed ephemeral PostgreSQL/API checks for equal-timestamp pagination, cursor validation, public reads, missing records, switch role/scope/validation, repeated on/off, immutable ordering values and caller transaction preservation. SQL capture verified ordering reads do not use FOR UPDATE. All smoke data rolled back; no test file added to the project.
