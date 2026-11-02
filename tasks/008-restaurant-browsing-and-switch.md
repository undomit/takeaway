# 008 — Expose restaurant browsing and accepting-orders control

Status: planned

Depends on: [007](007-admin-onboarding.md)

Sources: DESIGN §§1 A7, 5, 7.11, 8; ADR 0001. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add public restaurant list/detail with delivery fee and accepting-orders flag. Use the task 1 keyset contract with stable created_at/id ordering for lists.

Add the staff-only accepting-orders operation, restricted to the caller's own restaurant. Out-of-scope staff get 404; other roles get 403. Update timestamps in PostgreSQL.

Expose restaurants.service.get_for_ordering using the caller's session, returning an immutable ordering view and enforcing accepting orders. It must not lock restaurant rows or commit when called from an order use case.

## Acceptance and verification

Test public list/detail, deterministic pagination including equal timestamps, missing resources and invalid cursors. Test switch on/off and the role/scope matrix for two restaurants. Verify get_for_ordering rejects nonaccepting restaurants with restaurant_not_accepting_orders and does not commit its caller's work.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
