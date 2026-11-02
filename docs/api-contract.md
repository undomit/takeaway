# Initial-release API contract

Status: implemented and verified through task 024 (2026-11-02). Contract defined in task 001.

This contract turns [DESIGN.md](../DESIGN.md) §§1, 4–8 into implementable HTTP behaviour using the terms in [GLOSSARY.MD](../GLOSSARY.MD). It preserves [ADR 0001](adr/0001-restaurant-scoped-staff-and-admin-role.md) (restaurant-scoped staff and separate admins), [ADR 0002](adr/0002-pooling-with-sync-sqlalchemy.md) (polling and synchronous persistence) and [ADR 0003](adr/0003-money-as-integer-minor-units.md) (integer money and a single configured currency).

The design remains the architectural source. The decisions at the end explicitly identify additions where it did not specify an API detail. The application, migrations and executable verification now implement this contract; the [release handoff](release-handoff.md) records acceptance evidence, including comparison with live OpenAPI.

## Common conventions

All business routes below have prefix `/api/v1`; health routes are `/healthz` and `/readyz` without that prefix. Requests and responses use JSON except OAuth2 login, which uses `application/x-www-form-urlencoded`, and successful `204` responses, which have no body. Examples use fictional accounts and EUR as an example configured currency.

Protected requests use `Authorization: Bearer <access_token>`. Every protected request reloads the account and checks activation and token version. Expired, invalid, revoked, missing-account and inactive-account tokens all fail with `401`. Roles and restaurant membership come from the account, never from client fields or JWT role claims. Customers cannot register as staff/admin. The first admin is bootstrapped with `python -m app.cli create-admin`; there is no public admin-creation route.

JWTs contain `sub` (decimal account ID as a string), `ver` (integer token version), `iat` and `exp`. They use HS256, expire in 30 days for customers and 12 hours for staff/admins, and have no refresh token. Passwords use Argon2. Responses and logs never contain passwords, hashes or access tokens except the token intentionally returned by successful login.

Timestamps are database-generated UTC `timestamptz`, serialised as RFC 3339 strings with `Z` and exactly six fractional digits, for example `2026-11-02T10:00:00.000000Z`. Normal updates use database `now()`; clients cannot submit timestamps. Currency is the configured three-uppercase-letter code and is copied to each order; clients do not choose it.

IDs other than order IDs are positive JSON integers representable by PostgreSQL signed BIGINT. Order IDs are UUIDs; the server creates random UUID v4 values. Paths with invalid IDs get standard `422` validation errors; valid IDs that do not exist get `404`. UUID responses and canonical input values use lowercase hyphenated form.

### Validation and normalisation

Unknown body fields are rejected with standard `422` validation errors, including nested objects. Examples: client-supplied order prices, totals, `paid`, role, restaurant membership, status or timestamps outside the explicitly writable fields. Unknown query parameters are also rejected with `422`; the supported query parameters are listed below. JSON numeric fields are strict: booleans, strings, fractional numbers and floating-point JSON literals such as `1250.0` are not accepted as integers. Query/path integers are parsed from decimal strings.

| Field | Rule |
| --- | --- |
| Monetary values | JSON integers named `*_minor`; nonnegative and at most `9007199254740991` (also safely representable by common JSON clients). Normal and sale unit prices must be positive. Each calculated line/subtotal/total must fit this same bound and PostgreSQL BIGINT; overflow gets `422`, not a database error. |
| Quantity | Integer from 1 through 20. |
| Order lines in a request | From 1 through 100 distinct `menu_item_id` values; duplicates are `422`, never merged. The response order is specified below. |
| `full_name`, restaurant/category/item `name` | Strip leading/trailing whitespace; 1–200 characters afterwards. |
| Email | Strip surrounding whitespace, validate email syntax, lowercase for storage/login/uniqueness; maximum 254 characters. No case-sensitive account distinction. |
| New passwords | 12–128 characters; preserve all characters, including whitespace. Current-password/login input is 1–128 characters and is never trimmed. |
| `slug` | 1–100 characters matching `[a-z0-9]+(?:-[a-z0-9]+)*`; unique among restaurants. |
| Item `description` | String up to 2000 characters; default `""`; null is invalid. Preserve supplied whitespace. |
| `position` | Integer 0–2147483647; default 0. Ties are allowed and resolved by category ID. |
| `notes` | String up to 2000 characters or null; default null. Preserve whitespace, including an empty string. |
| `reason` | String up to 1000 characters or null; trim surrounding whitespace; missing/null/blank becomes null. Required-reason rules apply after trimming. |
| Booleans | Strict JSON booleans; query `active` accepts only the literal strings `true` and `false`. |

Ordinary PATCH requests are nonempty partial objects. Omitted fields remain unchanged. Explicit null is allowed only where this contract says so. Every PATCH validates the entire resulting record before writing, and either succeeds completely or changes nothing. No endpoint hard-deletes domain records.

### Saved address and delivery address

The shared `Address` object is:

```json
{"address_line1":"10 Example Street","address_line2":null,"postcode":"AB1 2CD","phone":"+441234567890"}
```

`address_line1`, `postcode` and `phone` are required strings, trimmed and nonblank, with maxima 200, 32 and 32 characters. `address_line2` defaults to null; trim supplied strings, convert blank to null, and cap nonblank values at 200 characters. Phone and postcode are stored as supplied after trimming; no country-specific validation, geocoding, delivery-radius check or address verification is performed.

A customer profile has either one complete `saved_address` object or null. `PATCH /me` replaces the entire saved address when an object is supplied; partial address objects are invalid. `{"saved_address":null}` clears every saved-address/contact column. Omitting `saved_address` leaves it unchanged. Staff/admin profiles always return null and cannot write these fields.

In `POST /orders`, omitted or null `delivery_address` means use the customer's saved address. An object is a complete one-off delivery address; it does not modify the profile. If neither source exists, return `422 delivery_address_required`. Copy the address and phone into the order; do not retain a mutable reference to the profile. A partial one-off address is a validation error even if a saved address exists.

## Route and permission matrix

All rows except health routes use `/api/v1`. `Any` means any authenticated role; `Public` requires no token. Every protected route returns `401` for missing/invalid authentication. An authenticated role not listed gets `403 forbidden`. For staff-only writes, another restaurant or mismatched nested resource returns `404 not_found` after role checks. Public routes remain public even if the caller includes a token; they never return private account/order data.

| Method | Path | Allowed caller/scope | Success body | Success |
| --- | --- | --- | --- | --- |
| POST | `/auth/register` | Public; creates customer only | Account | 201 |
| POST | `/auth/token` | Public | Token | 200 |
| GET | `/me` | Any, self | Account | 200 |
| PATCH | `/me` | Customer, self | Account | 200 |
| POST | `/me/log-out-everywhere` | Any, self | None | 204 |
| POST | `/me/change-password` | Any, self | None | 204 |
| POST | `/users` | Admin; creates staff only | Account | 201 |
| PATCH | `/users/{uid}` | Admin; deactivation only | Account | 200 |
| GET | `/restaurants` | Public | Page of Restaurant | 200 |
| POST | `/restaurants` | Admin | Restaurant | 201 |
| GET | `/restaurants/{rid}` | Public | Restaurant | 200 |
| PATCH | `/restaurants/{rid}` | Admin | Restaurant | 200 |
| PATCH | `/restaurants/{rid}/accepting-orders` | Staff, own restaurant | Restaurant | 200 |
| GET | `/restaurants/{rid}/menu` | Public | Menu | 200 |
| POST | `/restaurants/{rid}/menu/categories` | Staff, own restaurant | MenuCategory | 201 |
| PATCH | `/restaurants/{rid}/menu/categories/{cid}` | Staff, own restaurant/category | MenuCategory | 200 |
| POST | `/restaurants/{rid}/menu/items` | Staff, own restaurant | MenuItem | 201 |
| PATCH | `/restaurants/{rid}/menu/items/{mid}` | Staff, own restaurant/item/category | MenuItem | 200 |
| PUT | `/restaurants/{rid}/menu/items/{mid}/sale-price` | Staff, own restaurant/item | MenuItem | 200 |
| POST | `/restaurants/{rid}/menu/items/{mid}/archive` | Staff, own restaurant/item | MenuItem | 200 |
| POST | `/orders` | Customer, self | CreationReceipt | 201 |
| GET | `/orders` | Customer: own; staff: own restaurant; admin: all | Page of OrderSummary | 200 |
| GET | `/orders?active=true` | Staff, own restaurant; complete active list | ActiveOrders | 200 |
| GET | `/orders/{oid}` | Customer: own; staff: own restaurant; admin: all | OrderDetail | 200 |
| POST | `/orders/{oid}/status-changes` | Customer/staff within scope, then transition rules | OrderDetail | 200 |
| GET | `/healthz` (no prefix) | Public, intended internal use | Health | 200 |
| GET | `/readyz` (no prefix) | Public, intended internal use | Health | 200 or 503 |

No routes exist for account role changes, staff reassignment, reactivation, arbitrary order edits, menu category deletion, item unarchiving, refunds or real payments. An admin may read every order but cannot change any order status or use staff menu/accepting-orders routes. An admin may deactivate any account, including themselves; another admin or the bootstrap CLI is needed afterwards. No new special last-admin rule is introduced.

## Account operations and examples

`Account` has exactly `id`, `email`, `full_name`, `role`, `restaurant_id`, `is_active`, `saved_address` and `created_at`:

```json
{"id":10,"email":"customer@example.test","full_name":"Example Customer","role":"customer","restaurant_id":null,"is_active":true,"saved_address":null,"created_at":"2026-11-02T10:00:00.000000Z"}
```

| Operation | Request example | Response example/rule |
| --- | --- | --- |
| Register | `{"email":"customer@example.test","password":"example-passphrase","full_name":"Example Customer"}` | `201 Account` as above; starts active with no saved address. No automatic token. Duplicate email: `409 email_in_use`. |
| Login | Form body `username=customer%40example.test&password=example-passphrase` | `200 {"access_token":"<signed-jwt>","token_type":"bearer"}`. OAuth2 `username` carries email. Optional `grant_type` may only be `password`; optional `scope` must be empty. Other form fields are rejected. Bad credentials/inactive account: `401 invalid_credentials`. |
| Read profile | No body | `200 Account`; staff includes its `restaurant_id`, admin/customer has null. |
| Update profile | `{"full_name":"Updated Customer","saved_address":{"address_line1":"10 Example Street","postcode":"AB1 2CD","phone":"+441234567890"}}` | `200 Account` with updated name and complete saved address (`address_line2:null`). `{"saved_address":null}` clears it. Email/role/password are not writable here. |
| Log out everywhere | No body | `204`; atomically increment token_version, invalidating the current token and every other issued token. A new login is required. |
| Change password | `{"current_password":"example-passphrase","new_password":"replacement-passphrase"}` | `204`; verify current password, replace its hash and increment token_version atomically. Do not issue a replacement token; new login required. Wrong current password: `401 invalid_credentials`, no changes. |
| Create staff | `{"email":"staff@example.test","password":"example-passphrase","full_name":"Example Staff","restaurant_id":1}` | `201 Account` with `role:"staff"`, active, restaurant 1 and saved_address null. Missing restaurant: `404 not_found`; duplicate email: `409 email_in_use`. |
| Deactivate account | `{"is_active":false}` | `200 Account` with is_active false; increment token_version on first deactivation. Repeated deactivation returns the same inactive account without another increment. Only false is accepted; true or additional fields: `422`. Missing account: `404 not_found`. |

New-password rules apply to registration, onboarding and password change. Account deactivation and credential changes take effect on the next request, without waiting for JWT expiry. Successful password change is not idempotent: repeating it with the old current password fails. Logout/deactivation do not mutate past orders or status changes.

## Restaurant and menu operations

`Restaurant` has exactly `id`, `name`, `slug`, `delivery_fee_minor`, `is_accepting_orders`, `created_at`, `updated_at`:

```json
{"id":1,"name":"Example Restaurant","slug":"example-restaurant","delivery_fee_minor":250,"is_accepting_orders":false,"created_at":"2026-11-02T10:00:00.000000Z","updated_at":"2026-11-02T10:00:00.000000Z"}
```

| Operation | Request example | Response example/rule |
| --- | --- | --- |
| Create restaurant | `{"name":"Example Restaurant","slug":"example-restaurant","delivery_fee_minor":250}` | `201 Restaurant` above. Fee is required; zero is valid. Always starts not accepting orders. Duplicate slug: `409 slug_in_use`. |
| Edit restaurant | `{"name":"Renamed Restaurant","delivery_fee_minor":0}` | `200 Restaurant` with supplied fields updated. Writable fields: name, slug, delivery_fee_minor only. Admin cannot set accepting-orders here. |
| Read restaurant | No body | `200 Restaurant`; missing ID: `404 not_found`. |
| List restaurants | `?limit=50` | `200 {"items":[Restaurant],"next_cursor":null}`; pagination rules below. Restaurants not accepting orders remain visible. |
| Switch accepting orders | `{"is_accepting_orders":true}` | `200 Restaurant`; only writable field, required. Repeating the same value succeeds. |

`MenuCategory` has exactly `id`, `restaurant_id`, `name`, `position`. `MenuItem` has exactly `id`, `restaurant_id`, `category_id`, `name`, `description`, `price_minor`, `sale_price_minor`, `is_available`, `is_archived`, `updated_at`:

```json
{"id":3,"restaurant_id":1,"name":"Starters","position":0}
```

```json
{"id":7,"restaurant_id":1,"category_id":3,"name":"Example Soup","description":"Vegetable soup","price_minor":1250,"sale_price_minor":1063,"is_available":true,"is_archived":false,"updated_at":"2026-11-02T10:00:00.000000Z"}
```

| Operation | Request example | Response example/rule |
| --- | --- | --- |
| Create menu category | `{"name":"Starters","position":0}` | `201 MenuCategory`; omitted position is 0. |
| Edit menu category | `{"name":"Small plates","position":1}` | `200 MenuCategory`; name and position only. restaurant_id is never writable. |
| Create menu item | `{"category_id":3,"name":"Example Soup","description":"Vegetable soup","price_minor":1250}` | `201 MenuItem`; defaults: sale_price_minor null, is_available true, is_archived false. Allowed input fields: category_id, name, description, price_minor, is_available. Set sales through the sale-price route after creation. |
| Edit menu item | `{"category_id":3,"price_minor":1200,"sale_price_minor":null,"is_available":false}` | `200 MenuItem`. Writable: category_id, name, description, price_minor, is_available; sale_price_minor may additionally be supplied as a fixed integer/null to allow atomic price/sale changes. It cannot be a percentage on this route. |
| Set fixed sale price | `{"sale_price_minor":999}` | `200 MenuItem` with persisted sale_price_minor 999. |
| Set percentage sale price | `{"percentage_off":"15.00"}` | `200 MenuItem` with persisted sale_price_minor 1063 for normal price 1250. |
| Remove sale price | `{"sale_price_minor":null}` | `200 MenuItem` with sale_price_minor null; repeating removal succeeds. |
| Archive menu item | No body | `200 MenuItem` with is_archived true; repeating archive succeeds without modifying the item again. |
| Read menu | No body/query parameters | `200 Menu` as described below; missing restaurant: `404 not_found`. |

Sale-price PUT accepts exactly one of `sale_price_minor` or `percentage_off`; both or neither are `422`. `percentage_off` is a decimal **string**, no sign/exponent/whitespace, matching `(?:0|[1-9][0-9]?)(?:\.[0-9]{1,2})?`, with value strictly between 0 and 100. Numeric JSON percentages and precision beyond two places are rejected. Convert exactly to integer basis points (15.00% = 1500), then compute `floor((price_minor * (10000 - basis_points) + 5000) / 10000)` using integer arithmetic. Store only the resulting fixed sale price, not the percentage. The result must be positive and strictly below normal price. Thus 15% off 1250 gives 1063; values rounding to zero or to normal price are `422`. Checkout never rounds.

A normal-price edit retaining an existing sale must leave it valid. If the new normal price would be at/below the retained sale, return `422`; the request may instead explicitly clear/replace the sale in the same atomic PATCH. Omitted sale_price_minor retains it. No automatic recalculation or silent removal occurs.

Category and menu-item IDs must belong to the path restaurant, including a replacement category_id. A missing or mismatched category/item yields `404 not_found` on management routes. The database composite FK independently enforces category ownership. There is no category-moving or category-deletion operation.

Archiving permanently excludes a menu item from the public menu and checkout, preserving its ID and past order references. All later edits/sale changes to an archived item return `409 item_archived`; repeated archive remains successful. `is_archived:false` is never accepted in PATCH. Temporarily unavailable items stay visible and may be edited or made available again.

`Menu` is `{"restaurant_id":1,"categories":[...]}`. Each category is a MenuCategory object with an extra `items` array of MenuItem objects. Include empty categories. Categories sort ascending by `(position,id)`; items sort ascending by ID. No menu pagination is used: the nested menu is returned in full. No archived items appear; unavailable items appear with `is_available:false`.

For example, a minimal menu response is:

```json
{"restaurant_id":1,"categories":[{"id":3,"restaurant_id":1,"name":"Starters","position":0,"items":[{"id":7,"restaurant_id":1,"category_id":3,"name":"Example Soup","description":"Vegetable soup","price_minor":1250,"sale_price_minor":1063,"is_available":true,"is_archived":false,"updated_at":"2026-11-02T10:00:00.000000Z"}]}]}
```

## Placing an order and stable replay

`POST /orders` requires a customer token and exactly one `Idempotency-Key` header containing a hyphenated RFC 4122 UUID v4 (case-insensitive on input). Missing header: `400 idempotency_key_required`. Empty, duplicate, malformed or non-v4 header: standard `422` validation error. Keys are scoped to `(customer_id,key)` and retained for the order's lifetime. Another customer may independently use the same key.

Example request (the omitted delivery address uses the saved address):

```json
{"restaurant_id":1,"lines":[{"menu_item_id":7,"quantity":2}],"notes":"Ring once"}
```

The complete writable shape is restaurant_id, lines, delivery_address and notes. Each submitted line contains only menu_item_id and quantity. No customer ID or payment/price fields are accepted. A one-off request replaces delivery_address with a complete Address object. Order lines cannot span restaurants.

For a new key, require an existing restaurant (`404 not_found` otherwise), then accepting orders (`409 restaurant_not_accepting_orders`), then all requested items to be from that restaurant, nonarchived and available. Any missing, foreign, archived or unavailable requested item gets the same `409 item_unavailable`, without revealing its other restaurant. Resolve address, price on the server, call the mock gateway and create the order, order lines and initial status change atomically. Success means `paid:true`, status pending and one initial `from_status:null` status change made by the customer. No rows survive a payment decline or exception.

A restaurant switching accepting orders off or a menu price changing after it was read need not prevent this request committing. Snapshot the values read; do not lock restaurant/menu rows to impose stronger semantics. Existing order snapshots never change when a menu item, fee, name or saved address changes.

### CreationReceipt

The successful creation response has exactly the fields in this example:

```json
{
  "id":"c0ab74bf-01ce-4a10-8ed2-fadf52d84fd4",
  "restaurant_id":1,
  "status":"pending",
  "currency":"EUR",
  "paid":true,
  "delivery_address":{"address_line1":"10 Example Street","address_line2":null,"postcode":"AB1 2CD","phone":"+441234567890"},
  "notes":"Ring once",
  "lines":[{"id":21,"menu_item_id":7,"item_name":"Example Soup","unit_price_minor":1063,"original_unit_price_minor":1250,"quantity":2,"line_total_minor":2126}],
  "subtotal_minor":2126,
  "delivery_fee_minor":250,
  "total_minor":2376,
  "created_at":"2026-11-02T10:00:00.000000Z"
}
```

Lines sort ascending by the persisted order-line ID on **all** responses, including the first response. This avoids needing an additional stored request-position column. The original request's line-array order still participates in hashing. Monetary arithmetic is `line_total = unit_price * quantity`, `subtotal = sum(line_total)`, `total = subtotal + copied delivery_fee`. Original unit price always records the normal menu price; charged unit price uses a sale if present.

Build the receipt from immutable snapshots and the initial status change; its status is always the initial pending status, even when replayed later. Do not include updated_at, refund_owed, current account/menu values or subsequent status history. Keep serialisation, field presence, array ordering and timestamp formatting identical on replay; normal JSON object-key ordering is not an API guarantee. Reconstructing this receipt requires no response-cache table or extra mutable JSON column.

The initial response is `201` without Idempotent-Replayed. Every matching replay is `201` with the same JSON body and `Idempotent-Replayed: true`. It does not call the gateway again or insert rows. No additional Location header is required.

### Canonical request hash

Validate the submitted body first, including unknown-field rejection, integer rules, duplicate-line detection and normalisation above. The model always expands missing optional fields: delivery_address null, notes null, and address_line2 null in any supplied address. Hash that validated **submitted** model before resolving a saved address or reading menu/restaurant values. Exclude authentication, customer ID, idempotency header, timestamps and all server-derived fields; customer ID is already part of the unique-key scope.

Use SHA-256 of UTF-8 JSON with object keys sorted recursively, no insignificant whitespace, `ensure_ascii=False`, `allow_nan=False`, and separators `(',',':')`. Preserve array order; normalise UUID input where applicable. No Unicode normalisation beyond the documented field trimming is performed. Store the lowercase hexadecimal digest. These are the canonical bytes for the request example:

```json
{"delivery_address":null,"lines":[{"menu_item_id":7,"quantity":2}],"notes":"Ring once","restaurant_id":1}
```

Omitted delivery_address and explicit null hash identically; both mean use the saved address at first successful creation. Omitted notes and explicit null hash identically; notes `""` and null differ. Omitted/null/blank address_line2 hash identically after normalisation. Reordered object keys hash identically. Reordering the line array, changing quantity, restaurant, non-normalised notes or a supplied delivery address changes the hash. Sending a complete address equal to the current saved address still differs from omitting it: the submitted intent differs.

After authentication, role/header/body validation, check the existing `(customer_id,key)` before re-reading mutable ordering data. Same hash: replay the original receipt even if the profile/address, menu, fee, accepting-orders switch or current order status changed. Different hash: `422 idempotency_key_reused`. Malformed retries still fail validation, and deactivated customers cannot replay using revoked tokens.

For two concurrent requests that pass the first lookup, the unique constraint chooses a winner. Flush the order's unique insert before calling the gateway; a losing duplicate request rolls back and loads the committed winner in a fresh transaction. Compare hashes, then replay or return idempotency_key_reused. Only that specific unique-constraint violation is treated this way; unrelated errors propagate through normal failure handling. Nothing about this mock-only flow makes external payments safe without the future payment lifecycle and recovery work in DESIGN Appendix C.

Failed requests do not reserve keys. An unavailable item returning 409 can later become available; retrying the same key then performs a new attempt. No failed-response cache or key-expiry job is introduced.

## Reading orders and polling

`GET /orders/{oid}` loads through the single scoped query: customer owns the order, staff belongs to its restaurant, admin may read all. A missing or invisible order is `404 not_found` with the same response. Scope applies to lines/history as well as the order itself.

`OrderDetail` contains every CreationReceipt field, replacing status with the **current** status, and adds exactly `customer_id`, `updated_at`, `refund_owed` and `status_changes`. It uses the copied address, never a current profile lookup. `refund_owed` is derived as `paid && status in {rejected,cancelled}`, with no refund column and no refund execution.

`status_changes` is the complete history in ascending `(created_at,id)` order. Each entry has id, from_status, to_status, actor_user_id, actor_role, reason and created_at. Initial from_status and reason are null. Example history after staff acceptance:

```json
[
  {"id":31,"from_status":null,"to_status":"pending","actor_user_id":10,"actor_role":"customer","reason":null,"created_at":"2026-11-02T10:00:00.000000Z"},
  {"id":32,"from_status":"pending","to_status":"accepted","actor_user_id":11,"actor_role":"staff","reason":null,"created_at":"2026-11-02T10:01:00.000000Z"}
]
```

`GET /orders` returns `{"items":[OrderSummary],"next_cursor":null}` under the same scope. `OrderSummary` has exactly id, customer_id, restaurant_id, status, currency, paid, subtotal_minor, delivery_fee_minor, total_minor, refund_owed, created_at and updated_at. It deliberately omits lines, notes, address/contact and history, which are in detail. No arbitrary customer_id/restaurant_id/status filters are accepted in this release.

`GET /orders?active=true` is staff-only and returns `{"items":[OrderSummary]}` for **every** own-restaurant order in pending, accepted, preparing or out_for_delivery, newest first by `(created_at,id)`. There is no next_cursor or truncation. Customers/admins get `403 forbidden` for active=true. Explicit cursor/limit parameters with active=true are `422`, even if empty or equal to a default. Omitted active or active=false uses normal paginated history for every role. updated_since is not supported.

Customers should poll order detail approximately every 10 seconds and stop at delivered/rejected/cancelled. Staff poll the complete active list approximately every 10 seconds; terminal orders disappear on the next poll. These GETs are side-effect free. Polling is not an incremental timestamp feed; there is no SSE/WebSocket endpoint.

### Keyset pagination

Restaurant lists and normal order lists accept only cursor and limit (plus active for order lists). Limit defaults to 50 and must be 1–100. Sort descending by `(created_at,id)`; after a cursor use the strict predicate `(created_at,id) < (cursor.created_at,cursor.id)` in PostgreSQL, using the appropriate integer/UUID ID type. Equal timestamps use ID as the deterministic tie-breaker. Fetch one extra row to detect a next page; next_cursor uses the last **returned** row only if another row exists, otherwise null. An empty list is `{"items":[],"next_cursor":null}`.

The cursor is unpadded base64url of compact UTF-8 JSON with exactly `v`, `resource`, `created_at`, `id`, for example the decoded order token below. `v` is 1; resource is `orders` or `restaurants`; id is the normal JSON ID type for that resource. created_at uses the exact UTC timestamp format above. Reject padded/noncanonical base64url, invalid JSON, unexpected/missing members, wrong versions/resources/types/timestamps, invalid IDs, empty cursors and tokens longer than 1024 characters as standard `422` query validation errors. The row referenced by a well-formed cursor need not still exist.

```json
{"v":1,"resource":"orders","created_at":"2026-11-02T10:00:00.000000Z","id":"c0ab74bf-01ce-4a10-8ed2-fadf52d84fd4"}
```

Cursor contents are position information, not authorisation and not secret. They need no signature: every query independently applies the authenticated scope before the cursor condition; supplying or altering a cursor cannot widen access. Newer orders inserted between pages do not change the older-page boundary. This does not promise a transactionally frozen list across HTTP requests. Category/item/menu/history arrays have the independent ordering specified above and do not take these cursors.

## Status changes and error precedence

`POST /orders/{oid}/status-changes` accepts exactly to_status and optional reason. Example: `{"to_status":"rejected","reason":"Kitchen unavailable"}`. Status values are pending, accepted, preparing, out_for_delivery, delivered, rejected and cancelled; unknown values are standard `422` validation errors. Success is `200 OrderDetail` with current status, updated_at and the newly appended history.

| From | To | Role within scope | Reason |
| --- | --- | --- | --- |
| none (placement only) | pending | Customer | None |
| pending | accepted | Staff | Optional |
| pending | rejected | Staff | Required |
| pending | cancelled | Customer | Optional |
| accepted | preparing | Staff | Optional |
| accepted | cancelled | Staff | Required |
| preparing | out_for_delivery | Staff | Optional |
| preparing | cancelled | Staff | Required |
| out_for_delivery | delivered | Staff | Optional |

The initial status change is created by placement, never by this route. Optional reasons, if supplied, are stored after trimming. Delivered, rejected and cancelled are terminal. A request to set the existing status is an invalid transition, not an idempotent no-op.

After authentication, endpoint role and request-schema validation, apply checks in this order:

1. Load within scope; absent/invisible is `404 not_found`.
2. Check whether the from/to pair exists; absent pair is `409 invalid_transition`.
3. Check whether the role is allowed for that pair; wrong role is `403 transition_not_permitted`.
4. Check required reason; null/blank is `422 reason_required`.
5. Run conditional UPDATE guarded by the status read. Zero updated rows is `409 status_conflict`.
6. Append the status change with authenticated actor ID/role and database timestamp, then commit once. An insert failure rolls the status update back.

Authentication must run before endpoint role checks, and endpoint role checks before resource lookup. For requests that are both schema-invalid and unauthorised, the precise precedence of FastAPI's schema validation versus authentication dependencies is not part of this contract; neither path may reveal resource existence. For valid requests, all scope/transition precedence above is mandatory. Admin requests to this write route are always forbidden; the pure transition table also gives admins no allowed moves.

A concurrent customer cancel and staff accept from pending yields one success and one `409 status_conflict` **when both read pending**. If a caller reads the already changed status instead, it gets the ordinary transition result for that status. Exactly one additional status change commits. A retry after an uncertain status-change response should GET the current order before acting again; creation Idempotency-Key support does not apply to this route.

## Errors and health responses

Domain errors have `{"detail":"Human-readable explanation","code":"machine_readable_code"}`. Detail wording is not stable; code and HTTP status are. Ordinary schema, header, path and query validation keeps FastAPI's standard `422 {"detail":[...]}` shape without a custom top-level code; its specific library-generated wording is not a client contract. Never return SQL, hashes, passwords or hidden-resource details.

| Status | Code/shape | Trigger |
| --- | --- | --- |
| 400 | idempotency_key_required | Missing order-creation header. |
| 401 | not_authenticated | Missing, malformed, expired, revoked or inactive-account bearer authentication; include WWW-Authenticate: Bearer. |
| 401 | invalid_credentials | Login fails or change-password current password is wrong; same generic detail for missing account/wrong password/inactive login. Include WWW-Authenticate: Bearer. |
| 403 | forbidden | Authenticated role cannot use endpoint/view. |
| 403 | transition_not_permitted | Visible order and known status pair, wrong role. |
| 404 | not_found | Missing resource or outside scope; identical shape/detail in both cases. |
| 409 | email_in_use / slug_in_use | Unique account email or restaurant slug conflict. |
| 409 | restaurant_not_accepting_orders | New placement while restaurant is not accepting orders. |
| 409 | item_unavailable | Missing, foreign, unavailable or archived checkout menu item. |
| 409 | item_archived | Editing or setting a sale on a permanently archived menu item. |
| 409 | invalid_transition | Status pair not permitted at all, including terminal or same-status change. |
| 409 | status_conflict | Concurrent status update changed the expected status. |
| 409 | payment_declined | Injected/mock-test gateway declines; transaction rolls back. Default gateway never declines. |
| 422 | idempotency_key_reused | Validated request hash differs for an existing customer/key. |
| 422 | delivery_address_required | Neither one-off nor saved address exists for new placement. |
| 422 | reason_required | An allowed role/pair requires a nonblank reason. |
| 422 | Standard validation shape | Invalid input, nullability, unknown fields, bounds, cursor or header format. |
| 503 | payment_unavailable | Gateway reports a temporary failure; rollback with no stored failed key. Unexpected implementation errors remain generic 500. |

Examples distinguishing the central boundaries:

- Customer creates an order without a key: 400 idempotency_key_required.
- Customer polls with a revoked token: 401 not_authenticated.
- Customer cancels a visible accepted order: 403 transition_not_permitted.
- Staff X acts on restaurant Y's order: 404 not_found, even when the requested transition would otherwise be valid.
- Customer cancels a visible delivered order: 409 invalid_transition (the pair is absent), not role failure.
- Staff rejects pending without a nonblank reason: 422 reason_required; no status/history mutation.

`GET /healthz` is `200 {"status":"ok"}` if the process can handle requests; it does not ping PostgreSQL. `GET /readyz` pings PostgreSQL and returns `200 {"status":"ready"}` or `503 {"status":"not_ready"}`; failure bodies do not disclose connection details. Health endpoints use this explicit shape rather than the domain-error envelope. They need no authentication and are intended for internal probes; deployment may restrict public access.

Nginx later enforces a 64 KiB body limit (`413`) and per-IP limits (`429`) of 5 login requests/minute with burst 10, and 10 POST /orders requests/minute. It must not apply the creation limit to GET polling or status-change routes. Proxy-generated response bodies are not covered by the application domain-error schema.

## Explicit additions and implementation constraints

| Decision | Basis and implementation consequence |
| --- | --- |
| Missing write-route paths, request/response fields and success statuses | Completes operations described in DESIGN §§3/8 but omitted from §5's endpoint table; the matrix above is the initial-release route inventory. |
| All-role password-change endpoint with current-password verification and token revocation | Explicitly requested by the user during planning. Existing logout/deactivation rules remain. |
| Stable creation receipt versus current OrderDetail | Implements DESIGN §7.3's same-body replay after mutable status changes. Immutable fields plus initial history suffice; no new response-cache table. |
| Hash defaults/nulls, UTF-8 canonicalisation and line-array order | Makes the validated-body SHA-256 rule deterministic without hashing subsequently mutable saved addresses or prices. |
| Strict integer input, safe JSON monetary bound, text/password lengths, at most 100 distinct lines, and percentage decimal strings | Concrete validation choices where the design gave only the main money/quantity rules. Integer intermediate arithmetic still checks final storage bounds; no floating-point pricing. |
| Initially not accepting orders; positive normal/sale prices; nonnegative delivery fee | Conservative onboarding and money defaults. Only staff enable accepting orders. |
| Whole-address replacement/clearing; null order address means saved-address fallback | Defines one saved address plus per-order copying without introducing an address resource/table. |
| Permanent item archiving, no category deletion/moving, atomic price/sale edits | Preserves references and glossary meaning; no hard deletion or silent sale changes. |
| Bounded keyset history and restaurant lists; complete staff active list; deterministic nested ordering | Fills cursor/order details while preserving ADR 0002's full active-list polling. |
| menu_item_id naming | Use menu_item_id in API, Python and schema. DESIGN §4's ER diagram says item_id; its prose and checkout contract use menu_item_id. This is a spelling reconciliation, not an extra relationship. |
| Shared sessions with one outer write commit | Cross-module reads call service functions and never commit their caller's transaction. Orders never query another module's repositories/tables directly. |
| Database-enforced append-only history | Use distinct migration-owner and runtime credentials. Runtime may SELECT/INSERT status changes, never UPDATE/DELETE/TRUNCATE or own the schema. Actor identity comes from authentication. |
| Gateway error codes and role-only staff creation/deactivation payloads | Completes HTTP behaviour around the mock payment seam and admin responsibilities without implementing a real provider, account reassignment or reactivation. |

No feature in DESIGN §11 or Appendix C is pulled into this release: no modifiers, opening-hours schedule, radius validation, stale-order scheduler, SSE, real payment/refund calls, outbox, multi-restaurant staff membership or retention/anonymisation implementation.

## Acceptance walkthroughs and coverage

These are review scenarios for this documentation task; later tasks implement them as executable tests.

| Scenario | Expected observation |
| --- | --- |
| Place with saved address, change item/name/sale/fee and saved address, then replay the same omitted-address request | Identical 201 receipt with Idempotent-Replayed: true, original snapshots and total; one order/payment call. GET detail also retains the original address/prices. |
| Accept that order, then replay placement again | Receipt still says pending and excludes later history/updated_at; GET detail says accepted and includes initial plus acceptance status changes. |
| Reuse the same key with another quantity or explicit address | 422 idempotency_key_reused; no new order or payment. |
| Reorder JSON object members, or add optional delivery_address:null | Same canonical hash and replay. |
| Reorder lines or change notes null to empty string | Different hash; 422 idempotency_key_reused for an already used key. |
| Customer/admin/staff changes their password successfully | 204; all old tokens fail 401 on the next request, old password fails login and new password succeeds. Wrong current password leaves account/token_version unchanged. |
| Staff X substitutes restaurant Y's path/item/category/order ID | 404 for otherwise role-allowed writes/reads, no data leakage or mutation. Customer attempting a staff endpoint gets 403. |
| Two requests read pending and race accept/cancel | One 200, one 409 status_conflict; exactly two total history rows (placement plus winner). |
| Two concurrent matching placements share customer/key | Both receive the same 201 receipt, one marked replay; one persisted order, one initial status change and one gateway call. |
| Active kitchen list contains over 50 orders | Every active order is returned; terminal orders are absent. Cursor/limit on this view is 422. |
| API integer money and percentage rounding | Fractional/boolean prices are 422; 15.00% off 1250 persists 1063; order-time pricing sums integer snapshots only. |

| Design requirement | Contract location |
| --- | --- |
| §1 A1, §5 register/login/me/logout; §8 account permissions | Account operations and route matrix, including staff onboarding/deactivation and password change. |
| §1 A4–A7, §4 menu/restaurant constraints; §8 restaurant/menu writes | Validation, Restaurant and menu operations, sale rounding and archive rules. |
| §1 A2–A5/A10, §7.2–7.4, §7.10–7.11 | Address rules, Placing an order, CreationReceipt, Canonical request hash. |
| §5 list/detail/active endpoints, §7.6 and ADR 0002 | Reading orders and polling; Keyset pagination. |
| §6 and §7.1/7.5/7.7–7.9; §8 scope/transition permissions | Route matrix, Status changes and error precedence, explicit database-history constraints. |
| §5 error table and health endpoints; §8 revocation | Errors and health responses; Account operations and acceptance walkthroughs. |

All §5 routes and §8 permissions have a corresponding matrix row and payload/response rule. This contract leaves production hostname/certificates, secrets and backup destinations to deployment configuration; they do not change HTTP behaviour.
