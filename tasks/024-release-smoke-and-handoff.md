# 024 — Verify the complete deployed backend and hand off

Status: complete

Depends on: [023](023-ci-and-architecture-checks.md)

Sources: DESIGN §§1–10; GLOSSARY.MD; all ADRs. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add a repeatable smoke script or collection against the Compose HTTPS entry point using disposable accounts/restaurants. Bootstrap admin; onboard a restaurant/staff; set delivery fee, menu and sale price; enable accepting orders; register customer/save address; place/replay order; progress and poll it; verify immutable receipt/current detail and access restrictions.

Include a rejected/cancelled order to show derived refund owed without issuing a real refund, password change/logout/deactivation, and successful health/readiness. Keep smoke data isolated without adding production deletion APIs.

Finish developer/operator README links, example requests, test commands, route matrix, migration/backup/restore instructions and configuration prerequisites. Record certificate/host/off-host backup destinations as deployment inputs, not blockers for local development.

Map each initial-release requirement to its implementing task/test and list deliberately deferred §11/Appendix C features. No frontend, real payments, SSE, scheduler, multi-restaurant membership, modifiers or retention implementation belongs to this release.

## Acceptance and verification

From an empty local deployment, a developer following the README can run migrations, create the first admin, execute the HTTPS smoke flow and run the complete test suite. Compare live OpenAPI with task 1's route matrix; every intended route is implemented and protected. Produce a concise acceptance checklist with passing evidence and explicit external deployment inputs; no hidden manual DB edits are needed.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Implementation and evidence (2026-11-02)

`scripts/release_smoke.py` starts a fresh migration-gated Compose HTTPS stack with generated secrets, a specifically trusted localhost certificate and disposable data. It bootstraps the actual admin CLI, onboards restaurant/staff, sets fee/menu/percentage sale/accepting-orders, saves a customer address, checks checkout/replay and immutable snapshots after edits, progresses/polls fulfilment, rejects/cancels paid orders with derived refund owed, tests scope and password/logout/deactivation revocation, and compares all 26 live OpenAPI operations with task 001's route matrix including unauthenticated calls to every protected operation. It spaces checkout requests to respect the actual limiter and always tears down its own resources.

GitHub Actions now runs release, runtime and proxy/backup/restore acceptance after the task 023 pipeline. The local host-development override fixes loopback DB publishing without changing production networking. README, contract, coverage and [handoff checklist](../docs/release-handoff.md) link setup, examples, route matrix, tests, migrations, operations, explicit external deployment inputs and deferred scope. Existing uncommitted README installation edits were preserved separately from this task's commit.

Verification:

- `sh scripts/ci.sh` from clean tracked task 023 source and a separate empty PostgreSQL database: 84 passed (46 unit, 29 integration, nine committed/concurrency), six import contracts/AST checks, negative import probes, fresh/predecessor migrations and negative schema-drift probe; production image built successfully. Task 023 GitHub Actions also passed.
- `uv run --locked python scripts/release_smoke.py --image takeaway-app:ci`: all HTTPS business-flow, snapshot/replay, refund-owed, revocation, health/readiness and 26-operation contract/authentication checks passed from an empty deployment.
- `uv run --locked python scripts/runtime_smoke.py --image takeaway-app:ci`: migration failure gate, private credentials/ports, non-root runtime, safe correlated JSON logs, readiness outage/recovery, PostgreSQL durability and graceful two-worker SIGTERM all passed.
- `uv run --locked python scripts/proxy_smoke.py --image takeaway-app:ci`: TLS/redirects/request IDs, gzip/body/rate limits, unrestricted polling, private app/db, actual verified SSH backup transfer/retention and isolated restore with snapshots/history all passed.
- `uv run --locked ruff check .`, `uv run --locked ruff format --check .` and `git diff --check`: passed.

Production hostname/certificates, deployment secrets and off-host backup/cron remain operator inputs. No live external production deployment was requested or performed.
