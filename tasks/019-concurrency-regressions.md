# 019 — Verify concurrent checkout and status changes

Status: planned

Depends on: [018](018-change-order-status.md)

Sources: DESIGN §§7.3, 7.5, 10. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add concurrency tests with separate connections/sessions and real commits; coordinate with barriers at the read/insert/update points rather than relying on sleeps. Use isolated seeded data and privileged cleanup; never reuse the savepoint fixture across threads.

Race customer cancellation against staff acceptance after both read pending. Race identical order placements with the same customer/key and then different bodies sharing a key. Verify two different customers can independently use the same UUID key.

If failures reveal bugs, fix their owning services in this task without changing the contract. Keep timeouts bounded and include useful thread/error diagnostics.

## Acceptance and verification

For cancel/accept, exactly one succeeds and one returns 409 status_conflict; history has exactly two rows including placement. Identical checkout requests both return 201 with identical receipts, exactly one order/line set/initial history exists and only one gateway call occurs. Mismatched bodies produce one winner and one 422, never a generic 500. Tests pass against PostgreSQL with the restricted runtime role and leave no committed fixture data.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
