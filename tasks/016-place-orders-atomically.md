# 016 — Implement atomic, idempotent order placement

Status: complete (new tests deferred at the user's request)

Depends on: [008](008-restaurant-browsing-and-switch.md), [012](012-order-pricing.md), [013](013-idempotency-request-contract.md), [014](014-order-storage-and-history-permissions.md), [015](015-mock-payment-gateway.md)

Sources: DESIGN §§1 A2–A5/A10, 5, 7.2–7.4, 7.10–7.11, 10; Appendix C. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

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


## Completion evidence — 2026-11-02

Published customer-only POST /orders with strict body/header/query validation, safe standard pricing-overflow errors, initial 201 receipt and replay header behavior. The service hashes validated submitted intent, resolves existing customer/key before mutable order data, then uses restaurant/menu/user services with the shared Session. Saved/one-off addresses, menu values, configured currency and fee are copied. Added read-only users.service.get_saved_address.

The service flushes the exact unique customer/key insert before gateway work, writes pending order/lines/initial customer history, checks the gateway outcome, validates the receipt and commits once. Decline/unavailable/exception/database failures roll back all rows and leave keys reusable. Only the named unique-insert violation is handled as a race: rollback, reload the winner in a fresh transaction, compare hash and replay/conflict without another gateway call. Matching replays use immutable snapshots/initial history even after mutable values or current status change. No restaurant/menu row locks, new migrations or test files were added.

Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, including PostgreSQL migration upgrade/check.
- `PYTHONPATH="$PWD:/tmp" .venv/bin/python /tmp/takeaway_smoke_016.py`: passed real-login/API happy path, saved/one-off/missing addresses, exact integer totals/rows/initial actor, stable replay after mutable menu/profile/fee/switch/current-status changes, changed-body key conflicts, closed/unavailable inputs, role/header/query/quantity validation and overflow. Injected decline/unavailable/gateway exception/history failure/unrelated integrity failure confirmed rollback and failed-key reuse. All data rolled back.
- `.venv/bin/python /tmp/takeaway_smoke_016_race.py`: passed two independent API clients/sessions with bounded barrier synchronization at insert. Identical requests produced two identical 201 receipts, one replay, one order/line/history and one gateway call. Different-body race produced 201/422 idempotency_key_reused with one gateway call. Another customer reused the same UUID independently. Final three complete orders matched three calls; isolated owner cleanup removed all committed smoke data.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed. New automated coverage remains deferred as requested.
