# Run locally

Run PostgreSQL in Docker and the API on your computer. This guide uses HTTP at `http://127.0.0.1:8000`; HTTPS deployment is covered in [deployment and operations](deployment-operations.md).

## 1. Install the prerequisites

- Install and start Docker Desktop (or Docker Engine with Compose v2 on Linux).
- Install uv. On macOS: `brew install uv`. For other systems, use the [uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
- Install Git if you have not already cloned the project.

Confirm Docker is running and uv is available:

```sh
docker info
docker compose version
uv --version
```

## 2. Get the project and install dependencies

If you have not cloned the repository:

```sh
git clone https://github.com/undomit/takeaway.git
cd takeaway
```

Run every command below from the repository root, the directory containing `pyproject.toml`:

```sh
uv python install 3.12
uv sync --locked
```

uv creates the Python environment automatically. No separate virtual-environment setup or activation is needed.

## 3. Create the local configuration once

For a new checkout, paste this whole block into your terminal. It creates `.env` from the example, generates the four secrets, and fills in the matching database URLs:

```sh
uv run --locked python - <<'PY'
import os
import secrets
from pathlib import Path

config = Path(".env.example").read_text()
for placeholder in (
    "REPLACE_WITH_A_RANDOM_SECRET",
    "REPLACE_WITH_BOOTSTRAP_PASSWORD",
    "REPLACE_WITH_MIGRATION_PASSWORD",
    "REPLACE_WITH_RUNTIME_PASSWORD",
):
    config = config.replace(placeholder, secrets.token_urlsafe(48))
with os.fdopen(os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
    file.write(config)
print("Created .env")
PY
```

If `.env` already exists, this command stops with `FileExistsError` and leaves it unchanged. Reuse the existing file if it already has working settings. Keep it private and out of Git. The default currency is EUR; payments are mocked.

## 4. Start PostgreSQL and apply migrations

Port `5432` must be available on your computer.

```sh
docker compose -p takeaway-dev -f docker-compose.yml -f docker-compose.local.yml up -d --wait db
uv run --locked alembic upgrade head
uv run --locked alembic check
```

The last command should report `No new upgrade operations detected.` If any command fails, fix it before continuing.

## 5. Start the API

```sh
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Leave this terminal running. In a second terminal, check the API:

```sh
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/readyz
```

Expect `{"status":"ok"}` and `{"status":"ready"}`. Open [the interactive API docs](http://127.0.0.1:8000/docs) in your browser. A fresh database has no accounts, restaurants or menu items.

## 6. Create the first admin

In the second terminal, from the repository root:

```sh
uv run --locked python -m app.cli create-admin --email admin@example.test --full-name "Local Admin"
```

Enter and confirm a password of 12–128 characters at the hidden prompts. Run this once for that email.

In the interactive API docs, click **Authorize**, use the admin email as the username and enter its password. You can now create a restaurant with `POST /api/v1/restaurants` and its staff with `POST /api/v1/users`. Customers sign up through `POST /api/v1/auth/register`. See [API examples and permissions](api-contract.md) for the request bodies and the rest of the ordering flow.

## Stop and start again

Stop the API with **Ctrl+C**, then stop PostgreSQL:

```sh
docker compose -p takeaway-dev -f docker-compose.yml -f docker-compose.local.yml down
```

Your data stays in Docker's named volume. To start again, repeat steps 4 and 5; keep the same `.env` and existing admin account. Do not add `-v` to the shutdown command unless you intend to delete the database.

## If something fails

| Problem | What to do |
| --- | --- |
| `uv: command not found` | Install uv, open a new terminal and retry `uv --version`. |
| Docker cannot connect to its daemon | Start Docker Desktop or your Docker Engine service. |
| Port `5432` is already in use | Stop the other local PostgreSQL/container using it, then retry step 4. |
| Database authentication fails | Check that `.env` matches the passwords used when this database was first created. Editing `.env` does not change passwords in an existing Docker volume. |
| API startup reports invalid settings | Check `.env` for unfilled `REPLACE_WITH_…` values. |
| `/readyz` fails | Check database status with `docker compose -p takeaway-dev -f docker-compose.yml -f docker-compose.local.yml ps` and rerun step 4. |

For tests and CI commands, see [CI and local checks](ci.md). For a disposable full HTTPS acceptance run, see [release handoff](release-handoff.md).
