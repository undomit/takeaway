# 010 — Implement fixed and percentage sale prices

Status: planned

Depends on: [009](009-menu-categories-and-items.md)

Sources: DESIGN §§4, 7.4, 10; ADR 0003. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add sale_price_minor and its strict positive/below-normal-price CHECK in a migration if not already introduced in task 9. Expose staff-owned setting/removal of a fixed sale price and percentage-to-price conversion per task 1.

Calculate percentage conversion once in the menu service with exact arithmetic and half-up rounding. Reject a result of zero or a price that is not a reduction. Never use floating-point money.

Define atomic normal-price edits: reject a retained sale price that becomes invalid, or accept an explicitly supplied valid replacement/removal in the same update. Return the persisted resulting price to staff; orders later only read fixed prices.

## Acceptance and verification

Unit-test 15% off 1250 = 1063, half-up ties, percentage bounds/precision and zero/equal-price rejection. Integration-test setting, replacing and clearing a sale; invalid normal-price changes; PostgreSQL checks and cross-restaurant permissions. Assert JSON monetary fields are integers.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
