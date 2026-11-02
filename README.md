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

Feature routers handle HTTP, services own use cases and their transactions, and repositories own only queries. Domain errors in `app/errors.py` are independent of HTTP; `app/exception_handlers.py` maps their categories to response statuses. Feature-specific errors subclass the appropriate category and define their machine code and safe detail. FastAPI request-validation handlers are left intact. The initial import-linter contracts protect core independence, HTTP-free domain errors and one-way orders/menu/restaurants imports; task 023 extends enforcement across the completed application.

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

All 40 foundation tests remain, while task 003 adds only three integration scenarios focused on transaction isolation, failed-request rollback/resource release and readiness during a database outage. Integration fixtures migrate/check with the owner account and run requests using restricted runtime credentials. They refuse any database name other than `takeaway_test`, mismatched owner/runtime database targets, shared owner/runtime accounts, runtime superusers and runtime schema-creation rights.

Use `db_session` and `client` for ordinary integration tests. Their outer transaction is rolled back at teardown; the Session uses `join_transaction_mode="create_savepoint"`, so service commits remain visible inside the test but cannot leak into later tests. `rollback_sessions`/`database_client` provide context-manager versions when one scenario needs to inspect teardown or run several isolated sessions. Client contexts clear dependency overrides on exit. Small factories live in `tests/factories.py`; the current test-only probe is in separate metadata/schema, not an application migration.

Real-commit/concurrency tests use `committed_session_factory` and `@pytest.mark.concurrency`; each thread opens its own Session/connection. Do not combine it with `db_session`/`client`. The fixture truncates test domain/probe data with owner credentials before and after, excluding `alembic_version`, so future append-only runtime restrictions do not obstruct cleanup. Run these tests serially against an exclusively used test database (no pytest-xdist or simultaneous suites).

```sh
uv run --locked pytest -m "integration and not concurrency" -W error
uv run --locked pytest -m concurrency -W error
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml down
```

`down` preserves the disposable test volume for the next run. If explicitly resetting that test environment is desired, `down -v` removes only that project's test data; never run that command against the development project. Do not combine the local and test overrides. Missing test configuration/DB access fails integration setup rather than silently skipping coverage.
