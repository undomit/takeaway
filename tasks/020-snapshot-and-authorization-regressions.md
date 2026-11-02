# 020 — Verify snapshots and the full authorization matrix

Status: planned

Depends on: [018](018-change-order-status.md)

Sources: DESIGN §§7.2, 7.8–7.11, 8, 10; all ADRs. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add cross-feature integration scenarios using real registration/login and two restaurants, two customers, two staff and an admin. Reuse the existing per-feature tests; fill gaps in a route/role/scope coverage matrix rather than duplicating them.

Place a sale-priced order with a saved address, then change item name/normal price/sale price, archive it, change delivery fee and edit/clear the saved address. Verify the order's complete financial/contact snapshots remain intact. Repeat with a one-off address.

Exercise every menu/order write and read boundary including nested IDs, token revocation/deactivation and admin read-only order access. Assert every error code/status matches the contract. Confirm no delete API is exposed.

## Acceptance and verification

Run the real-PostgreSQL integration suite; verify no auth dependency is mocked, no personal data leaks across scope, old snapshots survive all later edits and new orders use new values. Capture a completed coverage matrix mapping each §8 boundary and §10 scenario to a named test. Every previously uncovered boundary has a regression test.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
