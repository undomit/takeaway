# 003 — Add PostgreSQL, migrations and isolated test fixtures

Status: planned

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
