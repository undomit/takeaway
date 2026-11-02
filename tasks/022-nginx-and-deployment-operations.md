# 022 — Configure TLS, rate limits and operational procedures

Status: planned

Depends on: [021](021-container-runtime-and-observability.md)

Sources: DESIGN §9; §7.12; ADR 0002. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Configure Nginx as the sole public entry point on 80/443, with HTTPS redirects, certificate mounts, upstream app, forwarded headers and generated X-Request-ID. Trust forwarded client addresses only within the documented internal deployment boundary.

Limit /api/v1/auth/token to 5 requests/minute with burst 10 and POST /api/v1/orders to 10/minute; do not apply the order-create limit to GET polling or status changes. Set a deliberate 429 response, body limit 64k, timeouts/slow-client buffering and JSON gzip.

Document local certificate setup, production secret/certificate provisioning, startup/shutdown, expand-then-contract migration procedure, rollback limits and pool connection budget (at most 30 for two workers, plus operational connections).

Add a nightly host-cron pg_dump procedure with off-host retention configuration and a documented restore into a separate database. This operational cron is distinct from an application scheduler. Keep backup credentials out of committed files.

## Acceptance and verification

Run nginx -t and proxy smoke checks with local test certificates: HTTPS redirect, forwarded scheme/request IDs, valid API traffic, configured body rejection and gzip. Burst login/creation to verify 429 rules while polling remains allowed. Verify app/db are inaccessible externally. Perform a dump/restore into an isolated database and verify orders, snapshots and history; record exact steps and required operator inputs.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
