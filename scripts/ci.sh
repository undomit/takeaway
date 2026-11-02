#!/bin/sh
# Requires the dedicated test database; all commands match CI and local development.
set -eu
cd "$(dirname "$0")/.."
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
uv run --locked python scripts/check_architecture.py
uv run --locked python scripts/verify_architecture.py
uv run --locked pytest -m 'not integration and not concurrency' -W error
uv run --locked pytest -m 'integration and not concurrency' -W error
uv run --locked pytest -m concurrency -W error
docker build -t takeaway-app:ci .
uv run --locked python scripts/migration_smoke.py --image takeaway-app:ci
