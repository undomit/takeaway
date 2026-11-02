# 002 — Create the application foundation

Status: complete

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

## Completion evidence — 2026-11-02

Implemented Python 3.12 project metadata and `uv.lock`, feature packages/routers, `create_app()` and `app.main:app`, unprefixed `/healthz`, cached/injectable validated settings, placeholder-only environment configuration and secret/cache exclusions. Added HTTP-independent domain-error categories and central response mapping without overriding FastAPI's request-validation handler. Feature routers are composed under `/api/v1`; endpoint implementations remain in their feature tasks, and `/readyz` remains in task 003.

Added developer setup/run/check instructions in [README.md](../README.md). The locked TestClient dependency is httpx2, as recommended by the installed Starlette version and its current official documentation, avoiding the deprecated httpx fallback. Import-linter currently checks core independence, HTTP-free domain errors and one-way orders/menu/restaurants dependencies; full application boundary enforcement remains in task 023.

Verification passed on Python 3.12.16 with uv 0.13.6:

- Installed the final lock into a fresh environment with `UV_PROJECT_ENVIRONMENT=/tmp/takeaway-foundation-clean-002 uv sync --locked` (using a temporary uv cache/Python installation during this session).
- `/tmp/takeaway-foundation-clean-002/bin/python -m pytest -W error`: **40 passed**, with no database or real application secrets. Covers independent app instances, startup/dependency settings overrides, cached environment/dotenv precedence, invalid/missing settings, secret masking, health, every domain-error HTTP category, versioned router mounting and standard 422 validation.
- `.venv/bin/ruff check .`: passed.
- `.venv/bin/ruff format --check .`: passed, 23 Python files formatted; Markdown is excluded.
- `.venv/bin/lint-imports`: all three architecture contracts passed.
- `git diff --check`: passed. `git check-ignore` confirmed local dotenv variants, virtualenv and import-linter cache are ignored while `.env.example` remains trackable.

The equivalent repeatable local commands are `uv sync --locked`, `uv run --locked pytest -W error`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .` and `uv run --locked lint-imports`.
