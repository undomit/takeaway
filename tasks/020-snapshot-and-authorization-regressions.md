# 020 — Verify snapshots and the full authorization matrix

Status: complete

Depends on: [018](018-change-order-status.md)

Sources: DESIGN §§7.2, 7.8–7.11, 8, 10; all ADRs. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add cross-feature integration scenarios using real registration/login and two restaurants, two customers, two staff and an admin. Reuse the existing per-feature tests; fill gaps in a route/role/scope coverage matrix rather than duplicating them.

Place a sale-priced order with a saved address, then change item name/normal price/sale price, archive it, change delivery fee and edit/clear the saved address. Verify the order's complete financial/contact snapshots remain intact. Repeat with a one-off address.

Exercise every menu/order write and read boundary including nested IDs, token revocation/deactivation and admin read-only order access. Assert every error code/status matches the contract. Confirm no delete API is exposed.

## Acceptance and verification

Run the real-PostgreSQL integration suite; verify no auth dependency is mocked, no personal data leaks across scope, old snapshots survive all later edits and new orders use new values. Capture a completed coverage matrix mapping each §8 boundary and §10 scenario to a named test. Every previously uncovered boundary has a regression test.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Verification and coverage

The completed [coverage matrix](../docs/testing-coverage.md) maps every DESIGN §8 permission boundary and §10 scenario to named tests, reusing foundation/authentication and tasks 017–019 where coverage already exists. New cross-feature scenarios use real customer registration/login, admin onboarding of two restaurants/staff, and unmocked bearer authentication. Snapshot tests cover both saved and one-off addresses; token lifecycle covers all three roles; actual runtime SQL proves append-only permissions. Pure tests close deferred status/pricing/hash coverage, including all 147 status/role combinations.

A deterministic interleaving exposed a polling bug: an order read as pending could include a newly committed acceptance event. Detail now reads mutable status/timestamps/history in one scoped SQL statement; immutable lines remain separate. The regression proves a consistent earlier response and the new state on the next poll, without locking reads.

`uv run --locked pytest -W error -q` — 82 passed, including real-PostgreSQL and committed concurrency scenarios. `uv run --locked ruff check .`, `uv run --locked ruff format --check .` and `uv run --locked lint-imports` passed (3 contracts kept). Integration setup runs Alembic upgrade/check under migration-owner credentials and requests under restricted runtime credentials. No schema change was required.
