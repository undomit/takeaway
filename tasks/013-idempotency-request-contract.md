# 013 — Implement order validation and canonical request hashing

Status: complete (new tests deferred at the user's request)

Depends on: [006](006-profile-and-credential-management.md), [012](012-order-pricing.md)

Sources: DESIGN §§5, 7.3, 7.10, 10. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Define order-placement schemas for restaurant_id, menu_item_id/quantity lines, optional one-off delivery address and notes. Enforce UUID-v4 Idempotency-Key parsing with 400 idempotency_key_required when missing and task 1 errors for invalid values.

Implement SHA-256 over the canonical validated submitted body. Hash before resolving the saved address or loading menu prices; a profile/menu edit must not change the meaning of a retry. Follow task 1 rules for defaults/nulls, object keys and line-array order.

Define the stable creation-receipt serializer and current-detail schema as distinct responses. Both use the same immutable snapshot fields where relevant. This task supplies schemas/pure helpers; publishing POST /orders waits until task 16 includes complete idempotency.

## Acceptance and verification

Unit-test object-key reordering, nested address keys, different restaurant/quantity/address/notes and documented array/default/null treatment. Assert equivalent validated inputs hash identically, semantically changed inputs differ, and rejected client price fields never enter a hash. Test header parsing and response serialization without an orders endpoint or database.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Added strict placement input using shared quantity/ID/duplicate-line checks, optional complete address and whitespace-preserving notes. Extracted address validation into core with a compatible users.schemas export and frozen normalized addresses. Added canonical compact sorted UTF-8 JSON/SHA-256 helpers over submitted values only, with expanded optional defaults and preserved line-array order. Added pure exact-one UUID-v4 header parsing and an HTTP dependency with missing=400 and malformed/duplicate=standard 422 behavior.

Added shared immutable snapshot values and separate CreationReceipt/OrderDetail response schemas. Receipt serialization reads only immutable fields and initial customer history and stays pending/paid after later state changes. Lines/history sort deterministically, timestamps use six-digit UTC format, and current detail derives refund_owed. No production order endpoint, migration or test file was added; POST /orders remains task 016.

Verification:

- `.venv/bin/python /tmp/takeaway_smoke_013.py`: passed exact documented canonical bytes/digest, key/nested-address order equivalence, default/null/blank treatment, changed restaurant/quantity/address/notes/line-order differences, Unicode preservation without extra normalization, rejected client fields, strict header parsing and frozen/stable receipt versus current-detail serialization. Pure helpers imported no database/HTTP layer. An ephemeral FastAPI header probe verified missing=400, duplicate/invalid=standard safe 422 and uppercase UUID normalization without a database/order endpoint.
- `.venv/bin/python /tmp/takeaway_smoke_011.py` and `.venv/bin/python /tmp/takeaway_smoke_012.py`: passed again after integration of shared primitives.
- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, including PostgreSQL migration upgrade/check with no drift.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed. New automated coverage remains deferred as requested.
