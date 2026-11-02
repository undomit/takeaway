# Takeaway backend

A FastAPI modular monolith for a small restaurant ordering platform. The [design](docs/DESIGN.md), [glossary](docs/GLOSSARY.MD), [API contract](docs/api-contract.md) and [development tasks](tasks/README.md) define the release.

## TLDR

| I want to… | Read this |
| --- | --- |
| Run the backend on my computer | [Run locally](docs/run_locally.md) — prerequisites, setup, startup and shutdown |
| Understand the backend and its scope | [Design](docs/DESIGN.md) |
| Look up domain terms | [Glossary](docs/GLOSSARY.MD) |
| Find endpoints, permissions and request examples | [API contract](docs/api-contract.md) |
| Understand order statuses, polling and replay | [Order fulfilment](docs/order-fulfilment.md) |
| Run checks or understand architecture enforcement | [CI and local checks](docs/ci.md) |
| See what the tests cover | [Testing coverage](docs/testing-coverage.md) |
| Understand the Docker runtime and logs | [Container runtime](docs/container-runtime.md) |
| Deploy with HTTPS, run migrations or back up/restore | [Deployment and operations](docs/deployment-operations.md) |
| Verify the release and prepare an operator handoff | [Release handoff](docs/release-handoff.md) |
| Understand restaurant-scoped staff and admin roles | [ADR 0001](docs/adr/0001-restaurant-scoped-staff-and-admin-role.md) |
| Understand polling and synchronous persistence | [ADR 0002](docs/adr/0002-pooling-with-sync-sqlalchemy.md) |
| Understand integer money and currency snapshots | [ADR 0003](docs/adr/0003-money-as-integer-minor-units.md) |
| Browse the 24 completed implementation tasks | [Task index](tasks/README.md) — links to every task and its verification evidence |

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```sh
uv python install 3.12
uv sync --locked
cp .env.example .env
uv run --locked python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Replace JWT_SECRET in `.env` with the generated value and set PLATFORM_CURRENCY to the platform's three-letter uppercase currency code, such as EUR. The example JWT value is deliberately invalid. Keep `.env` private. JWT secrets must have at least 32 UTF-8 bytes, no surrounding whitespace and no placeholder prefix; use random generation rather than a memorable phrase. Secret values are masked in settings representations and validation messages. Currency validation checks format; selecting an actual supported currency is a deployment responsibility.

Python 3.12 is specified by `.python-version` and `requires-python`. Commit `uv.lock` when dependencies change. `uv sync --locked` installs the application and development tools from the lock and fails if the lock no longer matches pyproject.toml. Environment variables override `.env`. Required configuration is validated at application startup, not import time.

## Run and verify

```sh
uv run --locked uvicorn app.main:app --reload
```

`GET /healthz` returns `{"status":"ok"}`. OpenAPI is available at `/docs`. All initial-release business routes are implemented under `/api/v1`; see the [route and permission matrix](docs/api-contract.md#route-and-permission-matrix). `GET /readyz` returns `{"status":"ready"}` after a database ping, or `503 {"status":"not_ready"}` if PostgreSQL is unavailable. Liveness does not contact the database. The app creates its connection pool lazily and disposes it on shutdown.

Run the foundation checks without a running database or real secrets:

```sh
uv run --locked pytest -m "not integration and not concurrency"
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
```

TestClient uses the httpx2 dependency recommended by the current [Starlette documentation](https://starlette.dev/testclient/). Tests isolate environment settings, dotenv files and the settings cache. They use real FastAPI requests for health, domain-error mapping, standard 422 validation and versioned router mounting. Each app factory call has independent route registration, state and dependency overrides.

`app.core.config.get_settings()` is cached per process. Dependencies use `SettingsDep`; tests may set `application.dependency_overrides[get_settings]` before entering TestClient, or call `create_app(settings=Settings(...))`. Both startup validation and request dependency resolution honour the override. A direct `Settings(...)` also reads the environment/dotenv unless `_env_file=None` is specified. Clear `get_settings.cache_clear()` when deliberately changing environment configuration within one process.

Feature routers handle HTTP, services own use cases and their transactions, and repositories own only queries. Domain errors in `app/errors.py` are independent of HTTP; `app/exception_handlers.py` maps their categories to response statuses. Feature-specific errors subclass the appropriate category and define their machine code and safe detail. Validation errors retain FastAPI's standard detail-list shape; submitted input metadata is omitted so passwords and whole request bodies are not reflected in error responses. The initial import-linter contracts protect core independence, HTTP-free domain errors and one-way orders/menu/restaurants imports; task 023 [enforces boundaries across the completed application](docs/ci.md).

## PostgreSQL and migrations

Set distinct DB_BOOTSTRAP_PASSWORD, DB_MIGRATION_PASSWORD and DB_RUNTIME_PASSWORD values in `.env`, and update DATABASE_URL/MIGRATION_DATABASE_URL with the corresponding credentials. Generate URL-safe passwords or percent-encode reserved URL characters. The application reads only DATABASE_URL; Alembic reads only MIGRATION_DATABASE_URL and does not require JWT/currency settings. Both URLs require the `postgresql+psycopg` driver. Keep migration credentials out of the deployed app container.

For a host-run development app:

```sh
docker compose -p takeaway-dev -f docker-compose.yml -f docker-compose.local.yml up -d --wait db
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked uvicorn app.main:app --reload
```

The base Compose file publishes no database port; the local override binds only 127.0.0.1:5432. PostgreSQL 16 persists data in a named volume. The init SQL creates a separate non-superuser migration owner and restricted runtime account, revokes public schema creation and gives runtime schema usage and sequence access. It runs only on an empty volume: changing `.env` does not rotate existing PostgreSQL passwords. Apply credential changes explicitly to an existing database; do not discard development data to change them.

Set MIGRATION_RUNTIME_ROLE to the existing runtime login that should receive table grants (default: takeaway_runtime). It is a role name, not a URL or password, and must match the DATABASE_URL account. The test harness supplies its separate takeaway_test_runtime role explicitly; a direct test-database Alembic invocation must set MIGRATION_RUNTIME_ROLE=takeaway_test_runtime alongside its owner URL. Alembic quotes this identifier and does not create or promote roles.

Each new table migration must grant only the runtime DML needed for that table. There is intentionally no blanket default table-DML grant; runtime cannot modify `alembic_version`. In task 014, status-change history gets SELECT/INSERT only, with no UPDATE/DELETE/TRUNCATE. Migrations run as the owner; the runtime role cannot own/create application tables or manage roles.

Add each new feature's model import to `app/models.py` so Alembic sees complete Base.metadata. The initial revision is an empty baseline. Review autogenerated changes, use the configured constraint names (give CHECK constraints explicit semantic names), and run upgrade/check after each schema change. Later rolling deployments use expand-then-contract changes.

Requests share one synchronous Session through SessionDep, including nested dependencies/services. Only the outer write service commits. get_session rolls back failures and closes the session on every exit; successful requests without a commit also discard pending work. Each app worker has pool_size=10 and max_overflow=5, a 5-second pool checkout timeout and a 3-second PostgreSQL connect timeout. Connections use UTC; two workers may open at most 30 runtime connections, plus migrations/operations.

## Real PostgreSQL tests

The test stack has its own database name, roles, credentials, named volume and loopback port (55432). It does not use the development volume or application DATABASE_URL. Its committed passwords are explicitly disposable test-only values.

```sh
cp .env.test.example .env.test
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml up -d --wait db
uv run --locked pytest -W error
```

All 40 foundation tests remain. Task 003 adds three integration scenarios focused on transaction isolation, failed-request rollback/resource release and readiness during a database outage; task 004 adds two persistence scenarios for account identity, restaurant ownership, saved addresses and database constraints. Task 005 adds four authentication scenarios for signup/login, rejected or revoked tokens, role-specific expiration and admin bootstrap. Integration fixtures migrate/check with the owner account and run requests using restricted runtime credentials. They refuse any database name other than `takeaway_test`, mismatched owner/runtime database targets, shared owner/runtime accounts, runtime superusers and runtime schema-creation rights.

Use `db_session` and `client` for ordinary integration tests. Their outer transaction is rolled back at teardown; the Session uses `join_transaction_mode="create_savepoint"`, so service commits remain visible inside the test but cannot leak into later tests. `rollback_sessions`/`database_client` provide context-manager versions when one scenario needs to inspect teardown or run several isolated sessions. Client contexts clear dependency overrides on exit. Small factories live in `tests/factories.py`; the current test-only probe is in separate metadata/schema, not an application migration.

Real-commit/concurrency tests use `committed_session_factory` and `@pytest.mark.concurrency`; each thread opens its own Session/connection. Do not combine it with `db_session`/`client`. The fixture truncates test domain/probe data with owner credentials before and after, excluding `alembic_version`, so future append-only runtime restrictions do not obstruct cleanup. Run these tests serially against an exclusively used test database (no pytest-xdist or simultaneous suites).

```sh
uv run --locked pytest -m "integration and not concurrency" -W error
uv run --locked pytest -m concurrency -W error
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml down
```

`down` preserves the disposable test volume for the next run. If explicitly resetting that test environment is desired, `down -v` removes only that project's test data; never run that command against the development project. Do not combine the local and test overrides. Missing test configuration/DB access fails integration setup rather than silently skipping coverage.

## Restaurant and account storage

Revision 0002 adds Restaurant and User models with BIGINT identity IDs, integer delivery fees, database-generated UTC timestamps, account activation/token-version fields and one optional saved address. Restaurant updates made through SQLAlchemy use database `now()` for updated_at. New restaurants start not accepting orders; zero delivery fee is valid. Fees must fit the API's nonnegative safe JSON integer bound.

PostgreSQL enforces unique restaurant slugs and case-insensitive email identity, the customer/staff/admin role set, staff membership in exactly one existing restaurant, and customer-only saved-address fields. A saved address is either wholly absent or has address_line1/postcode/phone present (address_line2 is optional). Restaurant references use ON DELETE RESTRICT. The migration grants runtime SELECT/INSERT/UPDATE and identity-sequence access, without DELETE/TRUNCATE or access to migration bookkeeping.

Repositories perform only their feature's reads/inserts and never commit. `users.service.get_by_id` and `get_by_email` expose read-only lookups for subsequent authentication work; email lookup trims the submitted email and uses the same PostgreSQL lower() expression as the uniqueness index. They return None for missing accounts and include inactive accounts so authentication can explicitly reject them. Registration, credential authentication, profile management and admin restaurant/staff onboarding use this storage now.

## Registration, login and admin bootstrap

`POST /api/v1/auth/register` accepts email, full_name and password and returns a safe Account response with 201. It always creates an active customer with no restaurant or saved address. Extra fields such as role or restaurant_id are rejected. Email/name whitespace is stripped, email is normalised/lowercased and the PostgreSQL unique index resolves case-insensitive duplicates (409 email_in_use, including races). Email validation checks syntax only, permits reserved .test example addresses and does no DNS/delivery verification. Passwords contain 12–128 characters, preserve whitespace and are stored only as Argon2 hashes.

`POST /api/v1/auth/token` accepts an OAuth2 URL-encoded password form: username contains email and password is the unmodified password. Optional grant_type must be password; optional scope must be empty. Unknown form fields/query parameters are 422. Missing accounts, bad passwords and inactive accounts get the same 401 invalid_credentials response; no tokens are issued to inactive accounts. Successful responses contain access_token/token_type and disable caching.

Bearer tokens are HS256 JWTs containing only sub/ver/iat/exp. Customers receive 30 days; staff/admins receive 12 hours. CurrentUser verifies the signature, required claim types and expiry, reloads the account through users.service and checks activation/token_version on every request. Roles and restaurant membership come from the account, never from JWT claims; require_role then enforces endpoint roles. Protected-endpoint failures are 401 not_authenticated with WWW-Authenticate: Bearer. The authentication dependencies protect the profile/password/logout routes and are ready for staff/order endpoints in later tasks.

After configuring the application and running migrations, bootstrap an admin from a terminal:

```sh
uv run --locked python -m app.cli create-admin --email admin@example.test --full-name "Example Admin"
```

Omit email/name flags to be prompted. The CLI prompts for the password twice without echo and refuses visible-input fallback when no secure terminal is available. There is no password command-line option or public admin-registration endpoint. Success exits 0; duplicates/errors exit 1. Duplicate emails never overwrite credentials or promote existing customer accounts. Bootstrap uses DATABASE_URL (restricted runtime grants), not migration-owner credentials.

The four auth integration scenarios use real password hashing, form login and bearer dependencies; only their clock and CLI password input are controlled. Clock checks cover exact 12-hour/30-day boundaries without sleeps. Test-only protected probes exercise CurrentUser/require_role without introducing production routes. Registration/login responses and validation errors never include passwords or hashes. The implementation follows the [FastAPI JWT guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) and [PyJWT verification guidance](https://pyjwt.readthedocs.io/en/stable/usage.html).


## Profiles and credential management

`GET /api/v1/me` returns the safe Account response for any authenticated customer, staff or admin. `PATCH /api/v1/me` is customer-only and accepts a nonempty object containing `full_name` and/or `saved_address`. Names are trimmed and must contain 1–200 characters; explicit null is invalid. Email, role and restaurant membership are not writable here. Staff/admin PATCH requests return 403.

A supplied saved address replaces the entire address and contact phone. It requires nonblank trimmed `address_line1` (maximum 200 characters), `postcode` and `phone` (maximum 32 each). Optional `address_line2` is trimmed, capped at 200 characters and defaults to null; blank becomes null. Partial address objects and unknown fields are 422. Omitting `saved_address` preserves it; `{"saved_address":null}` clears all four stored address/contact fields. Profile changes commit together.

`POST /api/v1/me/change-password` accepts `current_password` (1–128 characters) and `new_password` (12–128 characters) for all three roles. Both preserve whitespace. A wrong current password returns 401 invalid_credentials without changing the password or token version. Success hashes the replacement and increments token_version in one transaction, returning an empty 204. `POST /api/v1/me/log-out-everywhere` takes no body, increments token_version and also returns an empty 204. Both operations revoke every existing token, including the one used for the request, and require a fresh login. Neither issues a replacement token.

Account writes lock and refresh the current account, then recheck activation and the authenticated token version before writing. This serializes competing writes and rejects a request whose token was revoked while it waited for the lock. Each write use case commits once and rolls back on failure. Account responses never include password hashes or token versions; unknown query parameters are rejected on all four routes. Task 006 adds no automated tests at the user's request; focused regression coverage is deferred to a later stage.


## Admin restaurant and staff onboarding

All four onboarding routes require an active admin bearer token. Missing/invalid authentication returns 401; authenticated customers and staff receive 403. Unknown query/body fields are rejected with 422. No onboarding route hard-deletes records.

`POST /api/v1/restaurants` accepts `name`, `slug` and `delivery_fee_minor` and returns 201 with the Restaurant response. Names are trimmed to 1–200 characters; slugs contain 1–100 lowercase letters/digits separated by single hyphens. Delivery fees are strict JSON integers from 0 through 9007199254740991. Restaurants start with `is_accepting_orders:false`. `PATCH /api/v1/restaurants/{rid}` accepts a nonempty partial object with those same fields; omitted fields remain unchanged and explicit nulls are invalid. Both routes reject `is_accepting_orders`; use the staff-only switch described below. Duplicate slugs return 409 slug_in_use, including conflicts during edits, with the whole write rolled back. Missing restaurants return 404 not_found. Restaurant responses include database-generated UTC created_at/updated_at timestamps with six fractional digits.

`POST /api/v1/users` accepts `email`, `full_name`, `password` and `restaurant_id`, returning 201 with the safe Account response. It reuses registration email/name/password validation and Argon2 hashing, always creates an active staff account for exactly one existing restaurant, and stores no saved address. Client-supplied roles, activation flags and address fields are rejected. Missing restaurants return 404 not_found; case-insensitive duplicate emails return 409 email_in_use. The users service checks restaurant existence through restaurants.service and owns the only commit.

`PATCH /api/v1/users/{uid}` accepts exactly `{"is_active":false}` and returns the safe Account response. It locks and refreshes the target account, marks it inactive and increments token_version on the first deactivation in one transaction. Repeating deactivation succeeds without another increment. The next protected request and subsequent login fail for that account. It applies to customers, staff and admins, including the acting admin; there is no last-admin exception. Missing accounts return 404 not_found. Reactivation, role edits, staff reassignment and additional PATCH fields are rejected. Path IDs and staff restaurant IDs must fit positive PostgreSQL BIGINT; JSON IDs are strict integers.

Task 007 adds no automated tests at the user's request. The existing suite and an ephemeral PostgreSQL/API smoke check passed; focused automated coverage remains deferred.


## Restaurant browsing and accepting orders

`GET /api/v1/restaurants` and `GET /api/v1/restaurants/{rid}` are public, including when an invalid bearer token is supplied. Lists return `items` and `next_cursor`, newest first by `(created_at,id)`. `limit` defaults to 50 (1–100); supply the returned cursor for older rows. Equal timestamps use descending ID. Cursors are strictly validated unpadded base64url positions with the contract's resource/version/UTC timestamp/ID shape; malformed, empty and wrong-resource cursors return standard 422 validation errors. Missing detail IDs return 404. Restaurants not accepting orders remain visible.

`PATCH /api/v1/restaurants/{rid}/accepting-orders` accepts exactly `{"is_accepting_orders":true}` or false from staff of that restaurant. Other restaurants return 404, customers/admins 403 and missing authentication 401. Strict booleans and unknown-field/query rejection apply. Repeating a value succeeds; changes use PostgreSQL updated_at timestamps. `restaurants.service.get_for_ordering(session,id)` returns an immutable ID/name/delivery-fee snapshot, raises 404 for missing restaurants or 409 restaurant_not_accepting_orders for a disabled switch, and neither locks rows nor commits. `get_for_staff` exposes the scoped restaurant lookup for menu management.


## Menu browsing and management

`GET /api/v1/restaurants/{rid}/menu` is public and returns all categories (including empty ones) sorted by `(position,id)`, with nonarchived items sorted by ID. Unavailable items remain visible with `is_available:false`; archived items are omitted. Missing restaurants return 404. No pagination/query parameters are accepted.

Staff manage their own restaurant through POST/PATCH `/restaurants/{rid}/menu/categories[/{cid}]`, POST/PATCH `/restaurants/{rid}/menu/items[/{mid}]`, and POST `/restaurants/{rid}/menu/items/{mid}/archive` (all under `/api/v1`). Creates return 201; edits/archive return 200. Category inputs contain a trimmed name and optional nonnegative position (default 0). Item creation requires category_id, trimmed name and positive integer price_minor; description defaults to an empty string and preserves whitespace, and strict is_available defaults to true. Item edits support those fields, preserve omissions and reject nulls/empty objects/unknown fields. Prices must fit 9007199254740991; IDs must fit positive BIGINT. Category ownership is checked for both existing resources and replacement category_id. Staff from another restaurant and substituted nested IDs get 404; customer/admin writes get 403; unauthenticated writes get 401.

Archiving is permanent through the API. Repeating archive succeeds without changing updated_at again; later edits return 409 item_archived. There are no delete/category-moving routes. Schema revision 0003 adds menu tables, the composite category/restaurant FK, nonarchived partial index and integer price checks. It includes the nullable sale_price_minor column and positive/below-normal-price constraint used by sale-price management below. Runtime grants allow SELECT/INSERT/UPDATE and sequence access, without DELETE/TRUNCATE.

`menu.service.get_orderable_items(session,restaurant_id,item_ids)` returns immutable ID/restaurant/name/normal-price/sale-price values in requested order. Missing, foreign, archived or unavailable items uniformly raise 409 item_unavailable. It does not lock rows or commit its caller's transaction. Menu write services lock and refresh mutable records, then commit once and roll back failures. New automated tests remain deferred as requested.


## Sale-price management

Own-restaurant staff use `PUT /api/v1/restaurants/{rid}/menu/items/{mid}/sale-price` with exactly one field: `{"sale_price_minor":999}`, `{"sale_price_minor":null}` to remove a sale, or `{"percentage_off":"15.00"}`. Both/neither fields and unknown fields/queries return standard 422 validation errors. Fixed sale prices must be positive strict JSON integers below the normal price; repeated removal succeeds. Percentages are strict decimal strings greater than 0 and less than 100, with at most two decimal places and no signs, exponents, leading zeros or whitespace. Numeric JSON percentages are invalid.

Percentage conversion happens once using integer basis points and half-up rounding: `(price_minor * (10000 - basis_points) + 5000) // 10000`. For normal price 1250, 15% yields 1063. Zero results and results equal to the normal price are rejected. Only the fixed resulting sale price is stored and returned; percentages are not retained or reapplied during ordering.

Item PATCH additionally accepts fixed `sale_price_minor` or null. Omission preserves the existing sale. Before writing, the service validates the resulting normal/sale pair under the item row lock. Lowering normal price to/below a retained sale returns standard 422 and rolls back the whole edit. A request may change the normal price and explicitly replace/clear its sale together. Neither price changes nor sale removal silently alter another field. Archived items reject both sale PUT and PATCH with 409 item_archived; role/scope checks remain 401/403/404. Migration 0003 already enforces sale positivity/below-normal bounds, so task 010 needs no further migration. New automated tests remain deferred as requested.


## Order status rules

Task 011 supplies pure status rules, without publishing order endpoints. `app.orders.status.Status` defines pending, accepted, preparing, out_for_delivery, delivered, rejected and cancelled, with immutable active/terminal sets. `orders.state_machine.check_transition(from_status,to_status,role,reason)` checks the immutable declarative transition table in contract order: unsupported pair gives invalid_transition, wrong role gives transition_not_permitted, and a missing/blank required reason gives reason_required. Successful results are immutable and contain the trimmed reason (blank becomes null). Resource visibility is the calling service's responsibility before invoking these rules. Request shape/length validation belongs to the HTTP input schemas.

Initial placement uses the separate `initial_status_change(role)` helper, which permits only customers and returns null → pending with no reason. Admins have no permitted status changes; terminal and same-status changes are invalid. Account roles now live in persistence-free `app.users.roles`; `app.users.models.Role` remains compatible. Reproduce the readable transition table with `.venv/bin/python -m app.orders.state_machine` and compare it with the API contract. No schema migration or new automated tests were added.


## Pure order pricing

Task 012 adds `orders.pricing.price_order(items,lines,delivery_fee_minor,currency)` without database/HTTP dependencies or order endpoints. The caller supplies server-loaded menu snapshots and the configured currency/restaurant fee; requested lines contain only strict menu_item_id and quantity. Lines must contain 1–100 distinct items, quantities 1–20, and matching server snapshots. Prices/quantities reject booleans, strings and floats. Normal unit prices are positive; sales must be positive and below normal.

Pricing copies names and normal prices, uses a fixed sale when present, multiplies charged price by quantity, sums the subtotal and adds the copied delivery fee. No percentages or floating-point money are involved. Every stored unit/line/subtotal/fee/total must fit 9007199254740991 (and therefore PostgreSQL BIGINT); invalid inputs or overflow raise Pydantic validation errors before persistence. Results are frozen `PricedLine`/`PricedOrder` snapshots with tuple lines. Input order is preserved internally; response serialization later orders persisted lines by database ID. Shared strict quantity/money/currency/selection definitions live in `orders.values`. New automated tests remain deferred as requested.


## Order request and replay contract primitives

Task 013 supplies schemas/helpers, without exposing POST /orders. `orders.schemas.OrderCreateIn` accepts only restaurant_id, 1–100 distinct ID/quantity lines, optional complete delivery_address and optional notes (up to 2000 characters, preserving whitespace). Strict IDs/quantities and unknown-field rejection apply at every nesting level. Missing address/notes expand to null; address_line2 expands to null and blank becomes null. Shared address validation now lives in persistence-free `core.address`, with a compatible users.schemas export; validated addresses are frozen.

`orders.idempotency.canonical_request_bytes(request)` emits compact UTF-8 JSON with recursively sorted object keys, preserved array order, expanded defaults, ensure_ascii=False and allow_nan=False. `request_hash` returns its lowercase SHA-256 digest. Call it on the validated submitted body before resolving a saved address or loading menu/fee values. Omitted/null address or notes hash equally; empty notes differ from null. Address trimming/blank-line normalization happens before hashing. Supplying a complete address differs from omitting it, even if it matches today's saved address. No profile/menu/auth/customer/header values enter the hash.

`parse_idempotency_key(values)` requires one hyphenated RFC 4122 UUID v4 and normalizes uppercase UUID input. Missing headers raise idempotency_key_required (400); empty, duplicate, malformed and non-v4 headers are invalid. The ready-to-use `orders.dependencies.IdempotencyKey` maps invalid headers to standard 422 header validation errors without reflecting input. Task 016 uses this dependency on atomic POST /orders.

`OrderSnapshot` shares immutable financial/address values between distinct CreationReceipt and OrderDetail schemas. Persisted lines sort by ID; history sorts by created_at/ID; timestamps serialize in UTC with exactly six fractional digits. `creation_receipt(snapshot,initial_change)` uses only immutable fields and customer placement history, always reports pending/paid and excludes current status, later history, updated_at, customer_id and refund_owed. A current detail can be its source without changing replay output. OrderDetail reports current status, customer_id, updated_at and complete history, deriving refund_owed for paid rejected/cancelled orders. No response-cache column or database migration is introduced. New automated tests remain deferred as requested.


## Order persistence and history permissions

Task 014 adds migration 0004 and Order/OrderLine/OrderStatusChange storage; task 016 publishes placement, and tasks 017–018 publish scoped reads and atomic status changes. Orders have random UUID IDs and a unique `(customer_id,idempotency_key)` constraint. They copy currency, monetary totals, delivery address/contact and notes, retain the canonical request hash, and use PostgreSQL UTC timestamps. Lines retain item name/charged/original prices, quantity and the `menu_item_id` FK (the design ER diagram's item_id spelling is intentionally standardized). Status changes retain actor identity/role, reason and database timestamp. Refund owed is derived from paid plus rejected/cancelled status, without a column.

PostgreSQL checks status/role sets, currency/hash shape, bounded amounts, quantity, price relationships, line/total arithmetic and initial history shape. One initial status change and one line per menu item/order are enforced by unique indexes/constraints. Subtotal-versus-line-sum validation remains the pricing/write service responsibility. Customer/restaurant history, partial active-order, order-line and chronological status-change indexes are present, with deterministic ID tie-breakers.

Runtime can SELECT/INSERT all three tables and use identity sequences. Only orders.status/updated_at can be updated; financial/contact snapshots and order lines have no runtime update permission. History UPDATE/DELETE/TRUNCATE is denied, and runtime cannot delete/truncate orders/lines or create schema objects. Migrations/isolated cleanup use owner credentials. Repositories only query/insert/flush; they never commit. No new test files were added.


## Mock payment gateway

Task 015 adds the synchronous `payments.gateway.PaymentGateway` protocol: `create_payment(order_id,amount_minor,currency,idempotency_key)` returns a frozen PaymentResult with paid/declined/unavailable outcome. MockPaymentGateway always returns paid. The gateway contains no HTTP or persistence work; the order use case owns rollback/commit and maps declined/unavailable outcomes to payment_declined (409) and payment_unavailable (503).

`PAYMENT_GATEWAY=mock` is the default and the only supported configuration; another value fails settings validation at startup. `payments.dependencies.get_payment_gateway` is overridable per app and produces the stateless mock. No external credentials are needed. Recording/declining fake behavior was verified temporarily; test fixtures/files remain deferred at the user's request. This seam is mock-only: a real provider requires DESIGN Appendix C's separate payment lifecycle, provider idempotency and recovery. No real charges, refunds, webhooks or workers are implemented.


## Atomic order placement and replay

`POST /api/v1/orders` is customer-only and returns 201 CreationReceipt. Send exactly one hyphenated UUID-v4 `Idempotency-Key` header and the validated restaurant_id/ID-quantity lines/optional delivery_address/notes body. The server hashes submitted intent before resolving mutable data, then looks up the customer/key. A matching retry returns the identical immutable creation receipt with `Idempotent-Replayed:true`, even if menu/profile/fees/accepting-orders/current status later change. The first response omits that header. A different validated body with the same key returns 422 idempotency_key_reused; malformed retries still fail validation. Keys are independent across customers.

New attempts check restaurant existence/accepting orders, then uniformly reject missing/foreign/archived/unavailable items. A complete one-off address is copied without changing the profile; omitted/null address copies the saved address via users.service. Missing both returns 422 delivery_address_required. Pricing uses configured currency, server-loaded normal/fixed-sale prices and the copied fee; overflows return standard 422 validation responses. No explicit restaurant/menu locks are taken.

The order service shares one Session across feature services and owns the only commit. It flushes the named customer/key unique insert before writing lines/initial history and calling the injected gateway. A losing duplicate insert rolls back and reloads the committed winner in a fresh transaction, then compares the hash and replays or returns idempotency_key_reused without calling the gateway. Only that exact unique-constraint violation receives replay handling. The full receipt is validated before committing. The inserted paid=true flag remains uncommitted until the gateway reports paid; declines (409 payment_declined), unavailable outcomes (503 payment_unavailable), unexpected exceptions and database failures roll everything back. Failed attempts reserve no key and may be retried.

A successful placement stores one pending order, financial/contact snapshots, ordered lines and one initial null→pending customer status change. Replay reconstructs the response from those immutable snapshots/initial event, with no response cache. `users.service.get_saved_address` is a read-only copy helper and never commits/locks. Order reads, polling and status-change endpoints are implemented in tasks 017–018, described below. This remains mock-only transaction handling; real external payments require the separate lifecycle/recovery design. No automated test files were added or modified for task 016.


## Order fulfilment and regression coverage

Tasks 017–020 complete order reads, polling and fulfilment verification. `GET /api/v1/orders` returns scoped keyset history; staff `?active=true` returns the complete active list without pagination. `GET /api/v1/orders/{oid}` returns current status, immutable snapshots and ordered history. Customers see their orders, staff their restaurant and admins all orders. Missing/invisible IDs both return 404. Detail reads fetch mutable status and history in one SQL statement, keeping the response consistent if a status change commits during polling.

`POST /api/v1/orders/{oid}/status-changes` is customer/staff-only and enforces the transition table after scope. Its expected-status UPDATE and one authenticated history entry commit together. A concurrent loser returns 409 status_conflict; history failure rolls back both the status and timestamp. Creation replay still returns the original pending receipt. No payment/refund operation runs during a status change.

Customers poll detail about every 10 seconds until terminal; staff poll the complete active list about every 10 seconds. See [order fulfilment](docs/order-fulfilment.md) for behavior and [the completed coverage matrix](docs/testing-coverage.md) for named tests against DESIGN §§8/10. Focused test coverage resumes for these tasks, including previously deferred core domain cases. The full suite has 85 passing tests, with real PostgreSQL, real JWT login, all 147 pure transition/role combinations, snapshot/permission/token/payment regressions and deterministic races on independent committed connections. Run the verification commands above; committed suites must run serially against the exclusive test database.


## Container runtime

Task 021 adds a non-root multi-stage application image with locked production dependencies, two Uvicorn workers, graceful SIGTERM handling and readiness/liveness probes. Compose gates the app on healthy PostgreSQL and a successful one-shot migration; app/runtime and migration-owner credentials stay separate. App/db ports are private and PostgreSQL uses its persistent named volume. JSON access logs carry safe request IDs, route templates, status and duration without private request data. See [container configuration and verification](docs/container-runtime.md); task 022 supplies [public TLS, proxy limits and backup/deployment operations](docs/deployment-operations.md).


## TLS proxy and operations

Task 022 makes nginx the sole public entry point on 80/443, with mounted certificates, HTTPS redirects, trusted forwarding/request-ID boundaries, 64 KiB body limits, buffering/timeouts and JSON gzip. Login allows 5 requests/minute with burst 10; POST /orders allows 10/minute. Both return deliberate 429s, while GET polling and status changes remain unrestricted by those limiters. The local TLS override publishes only loopback 8080/8443.

The [operations runbook](docs/deployment-operations.md) covers certificate/secret provisioning, migration reruns and expand-then-contract releases, rollback limits, the 30-connection runtime pool budget, nightly host-cron backups with verified SSH transfer/retention, and restore into a separate database. Run `python3 scripts/proxy_smoke.py --image takeaway-app:local` after building the image to verify TLS, proxy limits, actual backup transfer and snapshot/history restore in disposable resources. Production hostnames, credentials, certificates, backup destination and host cron remain operator configuration.


## CI and release acceptance

Use [the CI guide](docs/ci.md) for locked local/Actions commands and focused suites. The [release checklist and handoff](docs/release-handoff.md) provides an empty-deployment HTTPS acceptance flow, requirement-to-test map, operator inputs and deferred scope. After the documented test database setup:

```sh
sh scripts/ci.sh
uv run --locked python scripts/release_smoke.py --image takeaway-app:ci
uv run --locked python scripts/runtime_smoke.py --image takeaway-app:ci
uv run --locked python scripts/proxy_smoke.py --image takeaway-app:ci
```

The smoke scripts create and remove their own isolated Compose projects. Read [configuration prerequisites](docs/release-handoff.md#reproduce-from-an-empty-deployment) first. For API clients, use the [account/menu/order request examples](docs/api-contract.md) and [fulfilment guide](docs/order-fulfilment.md); for production releases, use [migration, TLS and backup/restore operations](docs/deployment-operations.md).
