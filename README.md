# Takeaway backend

A FastAPI modular monolith for a small restaurant ordering platform. The [design](DESIGN.md), [glossary](GLOSSARY.MD), [API contract](docs/api-contract.md) and [development tasks](tasks/README.md) define the release.

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

`GET /healthz` returns `{"status":"ok"}`. OpenAPI is available at `/docs`. The feature packages and `/api/v1` router composition are in place; business endpoints arrive in their numbered tasks. `GET /readyz` returns `{"status":"ready"}` after a database ping, or `503 {"status":"not_ready"}` if PostgreSQL is unavailable. Liveness does not contact the database. The app creates its connection pool lazily and disposes it on shutdown.

Run the foundation checks without a running database or real secrets:

```sh
uv run --locked pytest -m "not integration and not concurrency"
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
```

TestClient uses the httpx2 dependency recommended by the current [Starlette documentation](https://starlette.dev/testclient/). Tests isolate environment settings, dotenv files and the settings cache. They use real FastAPI requests for health, domain-error mapping, standard 422 validation and versioned router mounting. Each app factory call has independent route registration, state and dependency overrides.

`app.core.config.get_settings()` is cached per process. Dependencies use `SettingsDep`; tests may set `application.dependency_overrides[get_settings]` before entering TestClient, or call `create_app(settings=Settings(...))`. Both startup validation and request dependency resolution honour the override. A direct `Settings(...)` also reads the environment/dotenv unless `_env_file=None` is specified. Clear `get_settings.cache_clear()` when deliberately changing environment configuration within one process.

Feature routers handle HTTP, services own use cases and their transactions, and repositories own only queries. Domain errors in `app/errors.py` are independent of HTTP; `app/exception_handlers.py` maps their categories to response statuses. Feature-specific errors subclass the appropriate category and define their machine code and safe detail. Validation errors retain FastAPI's standard detail-list shape; submitted input metadata is omitted so passwords and whole request bodies are not reflected in error responses. The initial import-linter contracts protect core independence, HTTP-free domain errors and one-way orders/menu/restaurants imports; task 023 extends enforcement across the completed application.

## PostgreSQL and migrations

Set distinct DB_BOOTSTRAP_PASSWORD, DB_MIGRATION_PASSWORD and DB_RUNTIME_PASSWORD values in `.env`, and update DATABASE_URL/MIGRATION_DATABASE_URL with the corresponding credentials. Generate URL-safe passwords or percent-encode reserved URL characters. The application reads only DATABASE_URL; Alembic reads only MIGRATION_DATABASE_URL and does not require JWT/currency settings. Both URLs require the `postgresql+psycopg` driver. Keep migration credentials out of the future deployed app container.

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
