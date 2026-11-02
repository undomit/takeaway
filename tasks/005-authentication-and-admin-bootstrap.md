# 005 — Implement registration, login and admin bootstrap

Status: planned

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
