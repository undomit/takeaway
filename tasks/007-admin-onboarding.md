# 007 — Implement restaurant and staff onboarding

Status: planned

Depends on: [005](005-authentication-and-admin-bootstrap.md)

Sources: DESIGN §§3, 5, 8; ADR 0001. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement admin-only restaurant creation and editing, including name, slug and delivery fee. Keep the accepting-orders switch exclusive to staff; reject attempts to use admin editing to bypass it.

Implement admin-only staff creation for an existing restaurant and account deactivation using the contract paths. Staff always receive one restaurant and no saved address; onboarding cannot create extra admins or modify role through generic fields.

Validate the restaurant via restaurants.service, with no cross-module repository calls. Reuse the account/password primitives from task 5. Deactivation must take effect on the next authenticated request.

## Acceptance and verification

Test an admin creating two restaurants and staff for each, editing fees, and deactivating an account. Check duplicate slugs/emails, missing restaurants, invalid role/address fields, no hard deletion, and 401/403 for unauthenticated/customer/staff callers. Verify deactivation revokes access through real tokens.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
