# 002 — Create the application foundation

Status: planned

Depends on: [001](001-contract-and-decisions.md)

Sources: DESIGN §§2–3, 5; Appendix B. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add pyproject.toml, a reproducible dependency lock, Python 3.12 setup, feature packages, create_app() and app.main:app. Use FastAPI, Pydantic settings, synchronous SQLAlchemy 2, psycopg 3, Alembic, PyJWT and pwdlib/Argon2; add pytest/TestClient and architecture-check tooling.

Implement environment-based cached settings with injectable overrides, platform currency and JWT secret validation. Commit a placeholder-only .env.example and ignore secrets/generated files.

Define HTTP-independent DomainError classes and central handlers producing {detail, code}; preserve normal FastAPI request-validation responses. Mount business routers under /api/v1 and implement /healthz. Keep endpoints using blocking database work as def.

## Acceptance and verification

Install from the lock in a clean environment; import/create two independent app instances. Test settings overrides, invalid configuration, /healthz, a representative domain error and standard 422 validation. No database is needed for these tests.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
