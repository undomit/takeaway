# Container runtime

Task 021 supplies `db → migrate → app → nginx`. The app/migrate image uses `python:3.12-slim`, the locked production dependency set and a non-editable wheel, and runs as UID/GID 10001. uv and development tools stay in the builder. Only allowlisted source/build inputs enter the Docker context; dotenv files, VCS, tests and local environments are excluded. Rebuilding source forces the project wheel to refresh even when the uv cache is reused.

## Configuration and startup

Copy `.env.deploy.example` to a private file such as `.env.deploy` (mode 600). Generate a random JWT secret and three distinct URL-safe database passwords. Do not reuse example placeholders. `DATABASE_URL` and `MIGRATION_DATABASE_URL` from host-run development are intentionally not passed wholesale: Compose constructs separate container URLs against `db:5432`. The app gets only runtime credentials, JWT secret, currency and mock gateway configuration. Only the one-shot migrator receives the owner URL; it requires no JWT secret.

```sh
cp .env.deploy.example .env.deploy
chmod 600 .env.deploy
# Replace all placeholders before startup.
docker compose --env-file .env.deploy -p takeaway build
docker compose --env-file .env.deploy -p takeaway up -d --wait app
docker compose --env-file .env.deploy -p takeaway exec -T app python -m app.healthcheck
docker compose --env-file .env.deploy -p takeaway exec -T app python -m app.healthcheck --liveness
```

The database healthcheck precedes migration. App startup requires the migrator to exit successfully; a failed migration leaves it stopped. Fix the migration, rerun the same Compose startup and inspect the migrator logs before serving traffic. This dependency is a startup gate, not a continuously running migration controller. Deploying a new image/migration requires the explicit lifecycle described by task 022; do not assume a process restart reruns migrations.

The base configuration publishes no app/database ports. `database` and `proxy` are private internal networks: db/migrate/app use the database network, app/nginx use the proxy network, and only nginx attaches to the edge network. Task 022 adds public TLS listeners and the final proxy configuration; see [deployment operations](deployment-operations.md) for certificate provisioning before starting nginx. Use the existing local/test overrides and explicitly select `db` for host-run development/tests; never combine those overrides with production deployment.

Uvicorn is PID 1 and starts two workers. Exec-form CMD forwards SIGTERM; workers get 20 seconds to finish requests and Compose allows 30 seconds before killing the container. Pool size 10 plus overflow 5 per worker means at most 30 runtime connections, plus migrations/probes/operations. A named PostgreSQL volume survives restart and `down`; never use `down -v` on development or production data.

## Health and logging

The image healthcheck runs readiness every 10 seconds with a 10-second start period, five-second probe timeout and three retries. Readiness queries PostgreSQL and fails during an outage; `/healthz` and `--liveness` remain process-only. Container health does not itself restart an unhealthy process; restart policy applies to process exits. Monitor readiness and restore database service before returning traffic.

Each completed HTTP request writes a JSON record with UTC timestamp, request ID, method, route template, status and duration in milliseconds. A single safe `X-Request-ID` (1–64 ASCII letters/digits/underscore/hyphen) is propagated; absent, invalid or duplicate IDs are replaced with a generated value. Responses include the same ID, including unexpected-error responses. Nginx generates the ID at the deployment boundary. Unknown routes log `unmatched`, not user-supplied paths. Query strings, bodies, Authorization headers and contact values are not recorded. Uvicorn's duplicate access log is disabled; server lifecycle logs are JSON and exception tracebacks/SQL parameter dumps are suppressed. Use request IDs for correlation, and reproduce unexpected errors in a controlled environment rather than logging private inputs.

Only trusted deployment containers may join the proxy network. `--forwarded-allow-ips=*` trusts that private boundary; publishing the app or attaching untrusted containers invalidates it. Task 022 overwrites inbound forwarded headers and request IDs at nginx.

```sh
docker compose --env-file .env.deploy -p takeaway logs -f app migrate
```

## Reproducible verification

```sh
docker build -t takeaway-app:local .
python3 scripts/runtime_smoke.py --image takeaway-app:local
uv run --locked pytest -W error -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
```

The smoke script creates a randomly named Compose project with generated disposable credentials and no published ports, then removes only that project's containers/networks/volume. It checks failed-migration gating, successful migrations, non-root UID, private ports and credential separation, safe correlated logs, outage/readiness/liveness recovery, data persistence after restart and graceful shutdown of both workers. It never uses the development or existing test database.

Implementation references: [uv Docker builds](https://docs.astral.sh/uv/guides/integration/docker/), [Compose startup conditions](https://docs.docker.com/compose/how-tos/startup-order/).
