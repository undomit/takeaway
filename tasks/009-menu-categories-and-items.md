# 009 — Implement menu browsing and editing

Status: planned

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
