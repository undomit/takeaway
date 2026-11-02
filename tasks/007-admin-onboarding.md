# 007 — Implement restaurant and staff onboarding

Status: complete (implementation; new tests deferred at the user's request)

Depends on: [005](005-authentication-and-admin-bootstrap.md)

Sources: DESIGN §§3, 5, 8; ADR 0001. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement admin-only restaurant creation and editing, including name, slug and delivery fee. Keep the accepting-orders switch exclusive to staff; reject attempts to use admin editing to bypass it.

Implement admin-only staff creation for an existing restaurant and account deactivation using the contract paths. Staff always receive one restaurant and no saved address; onboarding cannot create extra admins or modify role through generic fields.

Validate the restaurant via restaurants.service, with no cross-module repository calls. Reuse the account/password primitives from task 5. Deactivation must take effect on the next authenticated request.

## Acceptance and verification

Test an admin creating two restaurants and staff for each, editing fees, and deactivating an account. Check duplicate slugs/emails, missing restaurants, invalid role/address fields, no hard deletion, and 401/403 for unauthenticated/customer/staff callers. Verify deactivation revokes access through real tokens.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Implemented admin-only POST /restaurants, PATCH /restaurants/{rid}, POST /users and PATCH /users/{uid} under /api/v1. Restaurant creation/editing accepts only name, slug and strict bounded integer delivery fees; restaurants start not accepting orders, and admin input cannot change the switch. Nonempty partial edits preserve omitted fields and reject nulls. Database uniqueness conflicts, including edit races, map to 409 slug_in_use with rollback. Responses use database-generated UTC timestamps.

Staff onboarding reuses the existing account/password primitives, checks restaurant existence through restaurants.service without committing that read, and creates active staff with exactly one restaurant and no saved address. Duplicate emails return 409 email_in_use. Role/address/activation injection is rejected. Account deactivation accepts only strict false, locks and refreshes the target, and atomically increments token_version only on first deactivation. Repeat deactivation is successful without another increment; existing tokens and later login fail. Any account may be deactivated, including the acting admin, while records and restaurant membership are retained. No schema changes or migrations were required.

Moved the empty-query schema into core with a compatibility export from auth and added shared bounded ID primitives. Write services own their commits/rollbacks; repositories only query/flush. No test files were added or modified, following the user's instruction to defer new tests. Focused automated regression coverage remains deferred.

Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed** against isolated PostgreSQL; fixture-managed Alembic upgrade/check reported no schema drift.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports` and `git diff --check`: passed; all three architecture contracts kept.
- Ephemeral `.venv/bin/python` / TestClient API smoke against PostgreSQL: created two restaurants and staff for each; verified trimmed names, initial switch state, UTC timestamp shape, fee edits/bounds, unknown fields/queries, null/empty PATCH rejection, strict IDs/booleans, missing records, duplicate slug/email conflicts, edit-conflict rollback, 401/403 on all four routes, repeated deactivation without another version increment, rejection of revoked tokens and inactive login, admin self-deactivation and retained records. All smoke data was rolled back; no test file was created.

See [README.md](../README.md#admin-restaurant-and-staff-onboarding) for request behaviour and permissions.
