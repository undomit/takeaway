# 022 — Configure TLS, rate limits and operational procedures

Status: complete

Depends on: [021](021-container-runtime-and-observability.md)

Sources: DESIGN §9; §7.12; ADR 0002. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Configure Nginx as the sole public entry point on 80/443, with HTTPS redirects, certificate mounts, upstream app, forwarded headers and generated X-Request-ID. Trust forwarded client addresses only within the documented internal deployment boundary.

Limit /api/v1/auth/token to 5 requests/minute with burst 10 and POST /api/v1/orders to 10/minute; do not apply the order-create limit to GET polling or status changes. Set a deliberate 429 response, body limit 64k, timeouts/slow-client buffering and JSON gzip.

Document local certificate setup, production secret/certificate provisioning, startup/shutdown, expand-then-contract migration procedure, rollback limits and pool connection budget (at most 30 for two workers, plus operational connections).

Add a nightly host-cron pg_dump procedure with off-host retention configuration and a documented restore into a separate database. This operational cron is distinct from an application scheduler. Keep backup credentials out of committed files.

## Acceptance and verification

Run nginx -t and proxy smoke checks with local test certificates: HTTPS redirect, forwarded scheme/request IDs, valid API traffic, configured body rejection and gzip. Burst login/creation to verify 429 rules while polling remains allowed. Verify app/db are inaccessible externally. Perform a dump/restore into an isolated database and verify orders, snapshots and history; record exact steps and required operator inputs.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Verification and operator handoff

`python3 scripts/proxy_smoke.py --image takeaway-app:task021` passed all six stages using a generated trusted-local certificate and a randomly named disposable Compose project. Checks include nginx -t, HTTP→HTTPS redirect, forwarded HTTPS scheme/host/port, generated request ID correlation, gzip, 64 KiB rejection, actual login/create 429s with spoofed forwarded-IP headers, unaffected repeated polling/status changes and private app/db ports. The actual backup script transferred a custom pg_dump archive over verified SSH to a separate disposable container; failure retained old local backups and success applied retention. Restore into a new database preserved the paid order, price/contact/currency snapshots and ordered history. Live/existing restore targets were refused. Test containers, named volume and SSH image were removed.

`sh -n scripts/backup.sh scripts/restore.sh` passed. `uv run --locked pytest -W error -q` — 84 passed. Ruff lint/format and all 3 import-linter contracts passed. Task 021's container lifecycle smoke remains passing against the final Compose graph.

The [operations runbook](../docs/deployment-operations.md) records exact local/production startup, certificate renewal, explicit migration reruns, expand-then-contract deployment, rollback limits, pool budget, nightly host-cron backup/retention and isolated restore steps. Actual production DNS/certificates/secrets, off-host SSH identity/storage/retention and cron installation are operator inputs; no production deployment or host cron was changed. Proxy-generated errors intentionally retain nginx's response shape, as allowed by the API contract.
