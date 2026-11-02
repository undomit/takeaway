# 006 — Implement profiles, password change and token revocation

Status: planned

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
