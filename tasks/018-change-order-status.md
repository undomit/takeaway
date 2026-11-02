# 018 — Implement atomic order status changes

Status: planned

Depends on: [011](011-order-status-rules.md), [017](017-order-reads-and-polling.md)

Sources: DESIGN §§5–6, 7.1, 7.5, 7.7–7.9, 8, 10. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Publish POST /orders/{oid}/status-changes for customer/staff only. Load via visible_to first, run pure transition checks, then conditional UPDATE by order id and expected current status with database now().

A zero-row update raises status_conflict. Insert exactly one matching status change in the same transaction, including actor ID/role/reason and database timestamp; commit once. No status change or timestamp edit survives a failure.

Keep initial snapshots immutable and make no gateway/refund calls. Return the agreed current response. Prevent generic mutation paths bypassing the transition table.

## Acceptance and verification

Exercise every allowed transition over HTTP with appropriate roles/reasons and verify current status/history/actor/refund owed. Test terminal and unsupported pairs as 409, supported pairs with wrong role as 403, missing required reason as 422, and foreign scope as 404 before transition validation. Admin requests are 403. Inject a history-write failure and prove status rolls back. After progressing an order, replay its original POST and verify unchanged creation receipt while GET shows the new status.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
