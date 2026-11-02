# 005 — Implement registration, login and admin bootstrap

Status: complete

Depends on: [004](004-restaurant-and-customer-storage.md)

Sources: DESIGN §§3, 5, 8; ADR 0001. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement Argon2 hashing, HS256 JWT encoding/decoding and claims sub/ver/iat/exp. Issue 30-day customer and 12-hour staff/admin tokens; keep role and restaurant out of tokens.

Add customer-only public registration and OAuth2 password-form login. Prevent role/restaurant privilege injection, handle case-insensitive email uniqueness and return generic invalid-credential responses.

Implement CurrentUser and require_role via auth dependencies, reloading the account through users.service every request and checking activation/token_version. Add python -m app.cli create-admin with secure password input and safe duplicate handling; no public admin registration.

## Acceptance and verification

Use real login in integration tests. Verify hashes are not plaintext and never returned; correct/incorrect passwords; malformed, tampered, expired, missing-claim and wrong-algorithm tokens; missing/inactive accounts; token-version mismatch; exact role-specific expiry using a fixed clock. Bootstrap an admin twice and confirm safe duplicate rejection. Verify registration cannot create staff/admin.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Completion evidence — 2026-11-02

Implemented Argon2 hashing, HS256 token issuance/verification with required sub/ver/iat/exp, strict subject/version/date claim validation, and fixed role-specific token lifetimes. CurrentUser reads bearer tokens in auth.dependencies and reloads users through users.service for activation/version/role checks; require_role enforces endpoint roles. Authentication/account use cases keep queries in their own repositories and have no HTTP exceptions.

Added public customer-only registration, strict OAuth2 form login, safe Account/Token response schemas, generic credential failures, race-safe case-insensitive duplicate handling and cache-disabled token responses. Unknown body/form/query inputs and role/restaurant injection are rejected. Standard 422 detail-list responses omit input metadata to prevent password/body reflection. Password fields use SecretStr internally and preserve whitespace; no password/hash appears in account output.

Added python -m app.cli create-admin with optional email/name flags, secure repeated password prompts, no password argument, explicit exit status and safe duplicate handling. Existing accounts are never overwritten/promoted. Profile/password/logout endpoints remain in task 006; no public admin route was added. Added locked python-multipart/email-validator dependencies for form parsing and syntax validation; email validation does not perform DNS/deliverability checks.

Added only four flow-focused integration scenarios: signup/login and credential privacy, invalid JWT/current-account revocation and role changes, exact customer/staff/admin expiry boundaries with a fixed clock, and admin bootstrap/repeated-email safety. Authentication is not mocked; test-only protected probes exercise dependencies until later production protected routes arrive.

Verification passed on Python 3.12.16 with real PostgreSQL 16.15:

- `uv sync --locked`: installed the updated dependency lock successfully.
- `.venv/bin/pytest tests/integration/test_authentication_flows.py -q -W error --tb=short`: **4 passed**.
- `.venv/bin/pytest -q -W error --tb=short`: **49 passed** (45 existing plus four new scenarios); integration setup also ran Alembic upgrade/check with no schema drift.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` and `.venv/bin/lint-imports`: passed; all three architecture contracts kept.
- `uv lock --check --offline`, `.venv/bin/python -m app.cli create-admin --help` and `git diff --check`: passed.

See [README.md](../README.md) for registration/login behaviour, token handling and secure admin-bootstrap instructions.
