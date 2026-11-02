# 016 — Implement atomic, idempotent order placement

Status: planned

Depends on: [008](008-restaurant-browsing-and-switch.md), [012](012-order-pricing.md), [013](013-idempotency-request-contract.md), [014](014-order-storage-and-history-permissions.md), [015](015-mock-payment-gateway.md)

Sources: DESIGN §§1 A2–A5/A10, 5, 7.2–7.4, 7.10–7.11, 10; Appendix C. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Publish customer-only POST /orders. First resolve customer/key/hash: return the original receipt on a matching replay and 422 idempotency_key_reused otherwise, before revalidating mutable restaurant/menu/profile data.

For a new request, use restaurants/menu/users services with the same session. Resolve a complete one-off address or copy the saved address; absent both yields delivery_address_required. A one-off address never edits the profile. Price from server values and copy all snapshots/currency/fee.

Write the pending order, lines and initial NULL→pending customer status change, call the gateway before commit, and commit once. A decline/exception rolls back everything. Derive refund owed from paid plus rejected/cancelled status; do not store a refund column.

Flush the unique customer/key insert before calling the gateway. Handle only that named unique-constraint violation as a replay race: roll back, reload the winner and compare hashes. Do not swallow unrelated integrity errors. Avoid calling the gateway on a replay or losing duplicate insert. Accept the documented concurrent restaurant/menu edit semantics without locks.

Return 201, the stable receipt and the replay header when appropriate; no initially unsafe/nonidempotent version of this endpoint should be merged.

## Acceptance and verification

API-test happy path, saved and one-off addresses, no address, closed restaurant, each unavailable/archived/foreign/missing item, quantities/duplicates, header errors, role rejection and integer totals. Assert one order, exact lines, one initial status change and paid=true. A fake decline or raised error leaves zero rows. Retry after changing menu prices/profile/accepting flag returns identical receipt without a second gateway call. A changed submitted body with the same key returns 422. Service tests inspect rollback after unexpected database failures.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
