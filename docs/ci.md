# CI and architecture verification

GitHub Actions runs `.github/workflows/ci.yml` for PRs and main pushes with read-only repository permissions. Test credentials come from `.env.test.example` and belong only to disposable local/CI databases; no deployment secrets are needed. Production credentials must be supplied by the deployment environment.

From a clean checkout with uv, Docker Compose v2 (supporting `!override`) and Python 3.12:

```sh
uv python install 3.12
cp .env.test.example .env.test
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml up -d --wait db
sh scripts/ci.sh
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml down
```

`ci.sh` uses locked installation, Ruff, import-linter, focused AST checks, a negative architecture probe, unit tests, rollback-isolated PostgreSQL tests and committed concurrency tests in sequence. Do not run suites concurrently against the same test database. Missing database configuration fails rather than skips tests. The test override makes its database network non-internal so Docker can publish the loopback test port; the production database network remains internal. Runtime requests retain separate restricted credentials, including append-only history checks.

It builds the production image, then `migration_smoke.py` creates a random Compose project with a new empty volume and generated credentials, upgrades directly to head, checks drift, downgrades one revision and upgrades back to head. It also appends an unrepresented model column in memory, requires `alembic check` to reject it, removes it and checks again. Its volume is always removed, including on failure. Existing development/test data is never downgraded. A future irreversible revision must supply an explicit predecessor fixture/upgrade smoke instead of assuming downgrade safety.

Architecture guards reject reverse feature dependencies, auth/users cycles, cross-feature repository/model imports, router SQL/commits, repository commits and direct HTTP imports in services. Cross-feature use cases call services; the persistence-free `users.identity.Principal` protocol exposes authenticated identity without importing another feature's ORM table. Only `app/models.py` may import foreign models for metadata registration; FKs use string table names. Core dependency aliases transitively import FastAPI, so HTTP-free service contracts forbid direct transport imports. AST checks supplement import-linter and report file/line diagnostics.

Review must also trace SQL expressions and any raw SQL, dynamic imports, aliases or helpers: static guards cannot prove table ownership for arbitrary Python or SQL strings. Repositories own their feature's tables; services compose reads on one session and only the outer write service commits. Reject attempts to bypass checks. Schema changes require an Alembic revision and explicit runtime grants. Review destructive changes using expand-then-contract: add compatible fields first, deploy compatible readers/writers, backfill, verify, then remove obsolete fields in a later release. A database downgrade is not an automatic production rollback strategy; see [operations](deployment-operations.md).

Focused commands (run `uv sync --locked` first):

```sh
uv run --locked pytest tests/unit -W error
uv run --locked pytest tests/integration/test_authentication_flows.py -W error
uv run --locked pytest -m concurrency -W error
uv run --locked lint-imports
uv run --locked python scripts/check_architecture.py
uv run --locked python scripts/verify_architecture.py
uv run --locked python scripts/migration_smoke.py --image takeaway-app:ci
```

Choose a specific test path from `rg --files tests` when investigating a feature. [Coverage](testing-coverage.md) maps requirements to regression cases.
