# 001 — Complete the implementation contract

Status: complete

Depends on: None

Sources: DESIGN §§1, 4–8; GLOSSARY.MD; all ADRs. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Write docs/api-contract.md covering the documented API plus the missing write endpoints: POST /orders; POST/PATCH restaurants; staff onboarding and deactivation; accepting-orders switch; category/item creation and editing; sale-price changes and archiving. Keep all business endpoints under /api/v1. Specify request/response examples, success statuses, errors and role/scope rules.

Include POST /me/change-password for every authenticated role, with current_password and new_password, current-password verification, no password echo and revocation of all existing tokens. This endpoint was explicitly requested during planning.

Adopt the recommended stable creation receipt for POST /orders: id, initial pending status, currency, copied delivery address/contact, notes, snapshotted order lines, totals and created_at. Build it only from immutable fields and the initial status change. Exclude mutable updated_at and subsequent history. A replay returns this same receipt with 201 and Idempotent-Replayed: true; GET detail returns current status/history. This recommendation matches DESIGN §7.3 without adding a response-cache table.

Specify canonical hashing of the validated submitted request before saved-address resolution. Preserve item-array order, normalise object-key order, and define omitted versus explicit-null semantics. Reject unexpected price/paid/role fields rather than silently accepting them.

Fill routine contract gaps explicitly: integer money/quantity validation and bounds; nonempty order; complete saved/one-off addresses; clearing a saved address; percentage input precision; cursor encoding, ordering, limits and invalid-cursor errors; deterministic menu/history ordering; response to invalid UUID keys; missing reason as 422 reason_required.

Document proposed conservative defaults: new restaurants do not accept orders until staff enable them; zero delivery fee allowed, normal/sale prices positive; archiving is irreversible; category editing cannot cross restaurants; no category deletion API. Define pagination for restaurant lists using created_at/id and menu categories by position/id. Reserve active=true for staff (403 for customers/admins); return the complete active list and reject cursor/limit parameters on that view rather than silently truncating it. Set deterministic newest-first order history with a strict created_at/id cursor, a default page size of 50, and an explicitly bounded maximum. Record choices as additions to, not silent rewrites of, the source design.

## Acceptance and verification

Review a route/permission matrix against every §5/§8 operation, including writes described outside the endpoint table. Walk through examples of replay after a status change and saved-address change, password revocation, and each 400/401/403/404/409/422 distinction. No required behaviour remains implicit.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Completion evidence — 2026-11-02

Implemented [docs/api-contract.md](../docs/api-contract.md): 27 route/view rows with role/scope rules, named response shapes, request/response examples, validation and canonical hashing, stable creation receipts, cursor rules, status changes, errors, explicit additions and requirement coverage.

Reviewed the route matrix against DESIGN §§5/8 and all three ADRs. Walked through replay after status/profile changes, all-role password revocation, address copying, role/scope/transition error precedence and concurrent checkout/status-change outcomes. These are documentation acceptance checks, not claims that application endpoints or API tests already exist.

Verification passed: `git diff --check`; Python standard-library checks parsed all 11 JSON examples, verified 27 unique route/view rows and local links/table structure, and checked receipt arithmetic, canonical JSON and the half-up rounding example. Reproduce the core example checks from the repository root:

```sh
python3 - <<'PYTHON'
import json, re
from pathlib import Path
p = Path("docs/api-contract.md")
text = p.read_text()
blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
values = [json.loads(block) for block in blocks]
assert len(values) == 11
for target in re.findall(r"\]\(([^)]+)\)", text):
    assert (p.parent / target).exists(), target
for table in re.findall(r"(?:^\|.*\n)+", text, re.M):
    assert len({len(row.split("|")) for row in table.strip().splitlines()}) == 1
matrix = text.split("## Route and permission matrix")[1].split("## Account operations")[0]
rows = [row for row in matrix.splitlines() if re.match(r"\| (GET|POST|PATCH|PUT) \|", row)]
assert len(rows) == len({tuple(row.split("|")[1:3]) for row in rows}) == 27
receipt = next(v for v in values if isinstance(v, dict) and "subtotal_minor" in v)
assert receipt["total_minor"] == receipt["subtotal_minor"] + receipt["delivery_fee_minor"]
assert receipt["subtotal_minor"] == sum(line["line_total_minor"] for line in receipt["lines"])
assert all(line["line_total_minor"] == line["unit_price_minor"] * line["quantity"] for line in receipt["lines"])
canonical = next(b for b in blocks if b.startswith('{"delivery_address":null'))
assert canonical == json.dumps(json.loads(canonical), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
assert (1250 * (10000 - 1500) + 5000) // 10000 == 1063
print("Contract example checks passed")
PYTHON
```
