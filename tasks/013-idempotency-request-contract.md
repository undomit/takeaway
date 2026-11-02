# 013 — Implement order validation and canonical request hashing

Status: planned

Depends on: [006](006-profile-and-credential-management.md), [012](012-order-pricing.md)

Sources: DESIGN §§5, 7.3, 7.10, 10. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Define order-placement schemas for restaurant_id, menu_item_id/quantity lines, optional one-off delivery address and notes. Enforce UUID-v4 Idempotency-Key parsing with 400 idempotency_key_required when missing and task 1 errors for invalid values.

Implement SHA-256 over the canonical validated submitted body. Hash before resolving the saved address or loading menu prices; a profile/menu edit must not change the meaning of a retry. Follow task 1 rules for defaults/nulls, object keys and line-array order.

Define the stable creation-receipt serializer and current-detail schema as distinct responses. Both use the same immutable snapshot fields where relevant. This task supplies schemas/pure helpers; publishing POST /orders waits until task 16 includes complete idempotency.

## Acceptance and verification

Unit-test object-key reordering, nested address keys, different restaurant/quantity/address/notes and documented array/default/null treatment. Assert equivalent validated inputs hash identically, semantically changed inputs differ, and rejected client price fields never enter a hash. Test header parsing and response serialization without an orders endpoint or database.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
