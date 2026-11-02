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

`GET /healthz` returns `{"status":"ok"}`. OpenAPI is available at `/docs`. The feature packages and `/api/v1` router composition are in place; business endpoints arrive in their numbered tasks. Database connections, migrations and `/readyz` are implemented in task 003.

Run the foundation checks without a running database or real secrets:

```sh
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
```

TestClient uses the httpx2 dependency recommended by the current [Starlette documentation](https://starlette.dev/testclient/). Tests isolate environment settings, dotenv files and the settings cache. They use real FastAPI requests for health, domain-error mapping, standard 422 validation and versioned router mounting. Each app factory call has independent route registration, state and dependency overrides.

`app.core.config.get_settings()` is cached per process. Dependencies use `SettingsDep`; tests may set `application.dependency_overrides[get_settings]` before entering TestClient, or call `create_app(settings=Settings(...))`. Both startup validation and request dependency resolution honour the override. A direct `Settings(...)` also reads the environment/dotenv unless `_env_file=None` is specified. Clear `get_settings.cache_clear()` when deliberately changing environment configuration within one process.

Feature routers handle HTTP, services own use cases and their transactions, and repositories own only queries. Domain errors in `app/errors.py` are independent of HTTP; `app/exception_handlers.py` maps their categories to response statuses. Feature-specific errors subclass the appropriate category and define their machine code and safe detail. FastAPI request-validation handlers are left intact. The initial import-linter contracts protect core independence, HTTP-free domain errors and one-way orders/menu/restaurants imports; task 023 extends enforcement across the completed application.
