# 006 — Implement profiles, password change and token revocation

Status: complete (implementation; new tests deferred at the user's request)

Depends on: [005](005-authentication-and-admin-bootstrap.md)

Sources: DESIGN §§1 A10–A11, 5, 8, 10; planning clarification. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add GET /me for all roles and customer-only PATCH /me for name and one saved address/contact phone. Apply task 1 completeness and clear semantics atomically. Never return password hashes.

Add POST /me/log-out-everywhere and POST /me/change-password for all roles. Verify current password before changing it; hash the replacement and increment token_version in the same transaction. Successful logout-everywhere also increments token_version. Require a new login afterwards.

Use users.service for write operations, with one commit and rollback on failures. Do not implement password reset, refresh tokens or email verification.

## Acceptance and verification

Test customer profile create/update/clear, all-role /me, staff/admin PATCH rejection and invalid address bodies. For customer/staff/admin, verify old tokens immediately fail after logout or password change and new credentials can log in. A wrong current password changes neither hash nor token_version. Assert secrets are absent from responses.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Implemented GET /me for all roles and customer-only PATCH /me with trimmed names, complete saved-address replacement, explicit-null address clearing and atomic profile writes. Nonempty partial requests preserve omitted fields; null names, incomplete addresses and unknown body/query fields are rejected. Responses use the existing safe Account schema.

Implemented all-role password change and logout-everywhere with empty 204 responses, one service-owned commit and rollback on failures. Password change verifies the current password, hashes the replacement and increments token_version together; incorrect current passwords return 401 invalid_credentials without mutation. Neither operation issues tokens. Account row locks refresh the authenticated identity and recheck activation/token_version after waiting, preventing concurrent credential writes from overwriting each other. Existing authentication rejects revoked tokens on subsequent requests. No schema changes or migrations were needed.

The user's explicit instruction for this task overrides the planned new-test requirement: no test files were added or modified. Focused automated regression coverage is deferred to a later stage. Existing tests and an ephemeral API smoke check provide the verification for this change.

Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed** on the isolated PostgreSQL test database; its fixtures also ran Alembic upgrade/check without schema drift. Initial attempts could not connect while sandbox access was restricted/the test container was stopped; rerunning after starting the dedicated test stack passed.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports` and `git diff --check`: passed; all three architecture contracts kept.
- Ephemeral Python/TestClient API smoke against PostgreSQL (all data rolled back, no test file added): customer/staff/admin profile reads and write permissions, address replacement/clear and invalid-body rejection, unknown-query rejection, wrong-current-password safety, successful password change, old-password rejection, fresh login, and token rejection after password change/logout.

See [README.md](../README.md#profiles-and-credential-management) for usage and transaction semantics.


## Deferred coverage follow-up — PR 024

`test_saved_address_replacement_is_atomic_and_clear_removes_all_contact_fields` in [profile flows](../tests/integration/test_profile_flows.py) now exercises real customer registration/login and PostgreSQL-backed profile writes. Invalid partial/blank-phone address replacements leave both name and address unchanged; a name-only update preserves the address; a complete replacement trims fields and clears omitted line 2; explicit null clearing preserves the name and removes all four stored address/contact columns.

Verification: `uv run --locked pytest tests/integration/test_profile_flows.py -W error -q` passed (one test); `uv run --locked pytest -W error -q` passed all 85 tests in 32.33 seconds. Ruff lint/format and `git diff --check` passed. The original test deferral above records the task's implementation history; this follow-up supplies the missing profile-specific regression.
