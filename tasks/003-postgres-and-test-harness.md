# 003 — Add PostgreSQL, migrations and isolated test fixtures

Status: complete

Depends on: [002](002-application-foundation.md)

Sources: DESIGN §§3–4, 9–10; ADR 0002. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement engine/sessionmaker, DeclarativeBase, constraint naming convention and SessionDep. One request shares one session; repositories never commit; only top-level write use cases commit. Nested read services reuse the caller session without committing. Close sessions and roll back failures.

Add Alembic configuration importing all model metadata, an initial empty revision if needed, and local/test Compose configurations with PostgreSQL 16. Separate test database credentials from development data. Set pool_size=10 and max_overflow=5 per worker.

Create TestClient, factories and real-PostgreSQL fixtures using external transactions and join_transaction_mode="create_savepoint"; reset dependency_overrides after each test. Add a concurrency marker and a separate committed-data fixture with privileged cleanup for later tests.

Implement /readyz with a database ping and a failure response. Establish separate migration-owner and restricted runtime credentials; actual history-table grants arrive with task 14.

## Acceptance and verification

Upgrade an empty test database and run alembic check. Demonstrate that a service commit inside a test is rolled back at teardown and data cannot leak into the next test. Verify session closure/rollback on exceptions and readiness success/failure without exposing connection secrets. Document exact local test commands.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Completion evidence — 2026-11-02

Implemented synchronous PostgreSQL engine/session infrastructure, Base with named constraints, request-scoped SessionDep, rollback/closure and shutdown disposal. Connections use UTC, pool_size=10/max_overflow=5 and bounded connection/pool timeouts. Runtime and migration settings use separately validated, masked URLs; Alembic does not require JWT settings.

Added PostgreSQL 16 base/local/test Compose configurations, an empty Alembic baseline and model registry, and a one-time psql init script establishing distinct restricted runtime/migration-owner credentials. Test database, roles, volume and host port are separate from development. Table DML is granted explicitly by future table migrations; sequence access is prepared now, and append-only history grants remain in task 014. `/readyz` reports database availability without leaking credentials; `/healthz` stays independent of PostgreSQL.

Added savepoint rollback sessions, TestClient overrides/cleanup, small probe factory and dedicated real-commit fixtures with owner cleanup for later concurrency tests. Following the user's test preference, this task adds only **three** integration scenarios covering committed-test isolation, failed-request rollback/connection release and readiness during database outage. Existing foundation tests are retained and adapted to required database configuration. The testing preference is recorded in the shared completion rules.

Verification against PostgreSQL 16.15 and Python 3.12.16:

- `docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml up -d --wait --wait-timeout 60 db`: passed on a fresh disposable test volume, including role initialisation.
- Integration setup ran `alembic upgrade head` on the initially empty database and `alembic check`, then verified that runtime is not a superuser and cannot create in the application schema.
- `MIGRATION_DATABASE_URL=<dedicated test owner URL> .venv/bin/alembic upgrade head`: passed; the equivalent `alembic check` reported no new upgrade operations.
- `.venv/bin/pytest -q -W error --tb=short`: **43 passed** (40 existing plus three new scenarios).
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` and `.venv/bin/lint-imports`: passed; all three import contracts kept.
- `uv lock --check --offline`: passed; no new dependencies needed.
- Both local and test Compose configurations passed `docker compose ... config --quiet`; `git diff --check` passed.

See [README.md](../README.md) for exact setup, test selection, migration, privilege and cleanup instructions. No domain tables or business routes were introduced in this task.
