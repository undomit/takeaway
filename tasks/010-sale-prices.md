# 010 — Implement fixed and percentage sale prices

Status: complete (new tests deferred at the user's request)

Depends on: [009](009-menu-categories-and-items.md)

Sources: DESIGN §§4, 7.4, 10; ADR 0003. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add sale_price_minor and its strict positive/below-normal-price CHECK in a migration if not already introduced in task 9. Expose staff-owned setting/removal of a fixed sale price and percentage-to-price conversion per task 1.

Calculate percentage conversion once in the menu service with exact arithmetic and half-up rounding. Reject a result of zero or a price that is not a reduction. Never use floating-point money.

Define atomic normal-price edits: reject a retained sale price that becomes invalid, or accept an explicitly supplied valid replacement/removal in the same update. Return the persisted resulting price to staff; orders later only read fixed prices.

## Acceptance and verification

Unit-test 15% off 1250 = 1063, half-up ties, percentage bounds/precision and zero/equal-price rejection. Integration-test setting, replacing and clearing a sale; invalid normal-price changes; PostgreSQL checks and cross-restaurant permissions. Assert JSON monetary fields are integers.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Added own-restaurant staff sale-price PUT supporting exactly one fixed-price/null or validated percentage string. Percentages convert once through integer basis points and half-up rounding, persisting only the resulting integer. Results of zero or no reduction are rejected. Item PATCH now supports atomic normal-price edits with explicit fixed sale replacement/removal; omitted sales are retained and the entire resulting pair is checked under the item lock before any write. Invalid pairs roll back all submitted changes and use the standard 422 detail-list response. Archived items reject sale changes; existing role/scope checks apply.

No migration was needed: task 009's migration 0003 already supplies sale storage and the strict positive/below-normal CHECK. No tests were added or modified, per the user's instruction. Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, including isolated PostgreSQL migration upgrade/check with no drift.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed.
- `PYTHONPATH="$PWD:/tmp" .venv/bin/python /tmp/takeaway_smoke_010.py`: passed ephemeral checks for 15% off 1250 = 1063, half-up ties, maximum-safe-integer arithmetic, strict percentage bounds/precision/types, zero/no-reduction rejection, fixed sale setting/replacement/removal, retained-sale preservation, invalid normal-edit rollback, atomic replacement/clear, role/scope/missing IDs, archived-item rejection, persisted snapshot values and direct PostgreSQL sale CHECK enforcement. All smoke data rolled back; no project test file added.
- Repeated `PYTHONPATH="$PWD:/tmp" .venv/bin/python /tmp/takeaway_smoke_009.py`: passed the menu lifecycle/permission/database-constraint smoke after extending price edits.
