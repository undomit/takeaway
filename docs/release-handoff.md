# Initial release acceptance and handoff

The initial backend implements tasks 001–024. The [API contract and route/permission matrix](api-contract.md#route-and-permission-matrix) is the client-facing reference; [order fulfilment](order-fulfilment.md) explains polling, history, replay and refund owed. The release is mock-paid only. No real charge or refund runs.

## Reproduce from an empty deployment

Prerequisites: Git, uv, Python 3.12, Docker with Compose v2 supporting `!override`, and OpenSSL with `-addext` (OpenSSL 3 is suitable). Proxy backup verification also needs host `ssh`, `scp` and `ssh-keygen`. Images/dependencies require network access on their first build. On macOS, install OpenSSL 3 and put its `bin` directory on PATH if the system OpenSSL lacks `-addext`.

From a clean checkout:

```sh
uv python install 3.12
uv sync --locked
cp .env.test.example .env.test
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml up -d --wait db
sh scripts/ci.sh
uv run --locked python scripts/release_smoke.py --image takeaway-app:ci
uv run --locked python scripts/runtime_smoke.py --image takeaway-app:ci
uv run --locked python scripts/proxy_smoke.py --image takeaway-app:ci
docker compose -p takeaway-test -f docker-compose.yml -f docker-compose.test.yml down
```

The release script creates a random Compose project and new empty database volume, generates secrets and a localhost certificate, starts migration-gated app/nginx, trusts that specific certificate and uses ephemeral loopback HTTPS ports. It bootstraps through `app.cli` (supplying getpass input inside the disposable container), then uses real HTTPS requests and JWT login for all application flows. There are no manual SQL edits or production deletion endpoints. It prints acceptance results and always removes its own containers/volumes. It deliberately spaces POST /orders calls by 6.2 seconds to respect the production rate limit. It never targets an existing deployment. Do not use Python `-O`, which disables the smoke assertions.

The runtime script checks failed migration gating, restricted credentials/private ports, non-root UID, request logging, PostgreSQL durability and graceful worker shutdown. The proxy script checks trusted TLS/redirects, request IDs, limits, unrestricted polling, real SSH backup transfer/retention and isolated restore with snapshot/history comparison. Both use their own disposable projects. See [CI](ci.md), [runtime](container-runtime.md) and [operations](deployment-operations.md) for details and individual commands. GitHub Actions repeats all these commands on PRs and main pushes.

## Acceptance checklist and requirement map

| Requirement | Implementation and repeatable evidence |
| --- | --- |
| API contract, validation/errors, all intended routes | 001–003; `release_smoke.verify_routes` compares the live HTTPS OpenAPI operation set, success statuses and bearer requirements against every row of task 001's route matrix, then calls each protected operation without authentication and requires 401. |
| Identity, admin bootstrap, registration/login, saved address, staff onboarding | 004–007; release smoke CLI bootstrap → real admin/staff/customer login → restaurant/staff creation → saved profile; [authentication regressions](../tests/integration/test_authentication_flows.py). |
| Scoped restaurant/menu/fee/sale/availability/archive | 008–010; release smoke sets/updates fee, category/item, 15% sale to 1063 minor units, accepting-orders, public menu and archive; [authorization/checkout matrix](testing-coverage.md). |
| State machine, integer pricing, strict intent, hashing and mock payment seam | 011–015; [pure regressions](../tests/unit/test_order_domain_regressions.py), [checkout regressions](../tests/integration/test_checkout_regressions.py), database constraints and restricted runtime history permissions. |
| Atomic checkout, immutable contact/financial snapshots, stable replay | 014/016; release smoke verifies 2376 total, changes profile/menu/fee, compares original receipt/replay and current detail; checkout and snapshot regressions include rollback, failures and independent keys. |
| Scoped history/detail, complete active polling, transitions and derived refund owed | 017–018; release smoke progresses pending → accepted → preparing → out_for_delivery → delivered, polls detail/active lists, rejects and cancels separate paid orders, checks history and refund owed; cross-customer/role/restaurant restrictions. |
| Concurrency, snapshots, complete authorization and token lifecycle | 019–020; nine committed/concurrency tests plus rollback-isolated integration suites. Release smoke checks password-change/logout/deactivation invalidates issued tokens and leaves admin history access intact. Named per-boundary coverage remains in the [regression matrix](testing-coverage.md). |
| Container migration gate, readiness, pools, JSON request IDs, shutdown | 021; `runtime_smoke.py` and [runtime runbook](container-runtime.md). Release smoke starts from an empty volume and requires healthy/ready endpoints. |
| TLS, method-specific limits, private production network, backup/restore | 022; `proxy_smoke.py`, real verified off-container SSH transfer and separate restore DB; [operations runbook](deployment-operations.md). Development/test overrides publish only loopback DB ports and enable host reachability; production keeps its internal network. |
| Locked CI, model/migration parity and module boundaries | 023; `sh scripts/ci.sh`, six import contracts/AST rules, negative forbidden-import and model-drift probes, empty/predecessor migration verification. |
| Complete deployed acceptance and documentation | 024; `release_smoke.py`, this checklist, linked setup/contract/operations/coverage guides. |

Verification on 2026-11-02: task 023's entire `sh scripts/ci.sh` passed from a clean tracked-source snapshot and a separate empty PostgreSQL database (84 tests: 46 unit, 29 integration, nine committed/concurrency), production image build, architecture probes and migration drift/predecessor checks. Task 024 execution evidence is recorded in [the completed task](../tasks/024-release-smoke-and-handoff.md).

## Operator inputs before external deployment

Provision the deployment hostname/DNS, publicly trusted TLS chain/private key, host firewall/ports 80/443, durable database storage, generated JWT/bootstrap/migration/runtime secrets, intended currency and exact application image revision. Use `.env.deploy.example` and the [deployment runbook](deployment-operations.md); bootstrap the first real admin in a secure interactive terminal. For backups, supply the off-host SSH destination/account/path, pinned host key, private key access, retention and host cron via `.env.backup.example`; rehearse restore and ensure monitoring detects failed backup jobs. Local acceptance generates disposable equivalents and needs none of these external inputs. Local self-signed TLS and a disposable SSH container demonstrate mechanisms; they do not verify a future production hostname or backup host.

Use expand-then-contract database changes and the documented migration-before-app sequence. App rollback is safe only while schema compatibility remains; restoring a database is a separate recovery operation. See [backup/restore and release procedure](deployment-operations.md).

## Deliberately deferred

DESIGN §11 and Appendix C remain future work: real payments/refunds/webhooks, payment lifecycle/outbox/recovery, scheduler/auto-reject, SSE/LISTEN/NOTIFY, workers, multi-host services, PgBouncer/replicas, external identity/refresh tokens, multi-restaurant staff membership, opening-hours schedules, modifiers, delivery-radius checks, expanded metrics/tracing and retention/anonymisation. There is no frontend. These are not acceptance gaps in the initial backend release.
