# 009 — Implement menu browsing and editing

Status: complete (new tests deferred at the user's request)

Depends on: [008](008-restaurant-browsing-and-switch.md)

Sources: DESIGN §§1 A6, 3–5, 7.9–7.10, 8; GLOSSARY.MD. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add MenuCategory/MenuItem models, repositories and migration with composite category/restaurant foreign key and supporting uniqueness. Add the partial nonarchived menu index and integer price constraints.

Implement staff-owned category/item creation and editing, category position, availability and irreversible archiving. Do not hard-delete entities. Scope existing items/categories as well as path restaurant IDs to prevent ID substitution.

Expose public menu categories and nonarchived menu items with deterministic ordering; unavailable items stay visible and flagged. Archived items cannot be resurrected through generic PATCH.

Provide menu.service.get_orderable_items(restaurant_id, item_ids), returning snapshot-ready values, rejecting missing/archived/unavailable/foreign items uniformly as item_unavailable, without committing the caller transaction.

## Acceptance and verification

Test category/item lifecycle, ordering, availability and archived-item exclusion. Verify the composite FK rejects cross-restaurant category assignment in SQL as well as through the API. Parametrise writes across all roles and two staff restaurants, including mismatched nested IDs. Verify public visibility of unavailable items. Run migration upgrade/check.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Added MenuCategory/MenuItem models, explicit migration 0003, scoped repositories, services and public/staff routes. Migration supplies the composite category/restaurant FK, supporting uniqueness, partial nonarchived index, positive bounded integer normal prices and nullable positive/below-normal sale prices. Runtime receives only SELECT/INSERT/UPDATE and sequence access. Models are registered with Alembic.

Public menus retain empty categories and unavailable items, omit archived items and sort categories by position/ID and items by ID. Staff writes enforce own restaurant and nested category/item scope, strict input validation and atomic partial edits. Archive is permanent and repeated archive preserves updated_at. Later archived-item edits fail with item_archived. Immutable get_orderable_items values reject missing/foreign/unavailable/archived IDs uniformly without locking/committing. Sale write operations remain task 010.

No tests were added or modified, as requested. Verification:

- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, with PostgreSQL migration upgrade/check and no drift.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed.
- Ephemeral owner-transaction Alembic downgrade to 0002, upgrade to head and check: passed; verification transaction rolled back to preserve the existing schema.
- `PYTHONPATH="$PWD:/tmp" .venv/bin/python /tmp/takeaway_smoke_009.py`: passed rollback-only PostgreSQL/API checks for category/item lifecycle and ordering, unavailable visibility, archive exclusion/repeat/edit rejection, strict inputs, all-role/two-restaurant write permissions, nested ID substitution, immutable ordering values and caller transaction preservation. Direct SQL/ORM writes confirmed composite FK/price constraints, and runtime lacks DELETE. All smoke data rolled back; no project test file added.
