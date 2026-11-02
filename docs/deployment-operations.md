# Deployment and operations

The release runs on one trusted Docker host: nginx is the sole public entry point on 80/443; app/db have no published ports. See [container runtime](container-runtime.md) for the non-root image, migration gate, health and request logs. These procedures operate the backend; they do not schedule application jobs or implement real payments/refunds.

## Required operator inputs

Provision Docker Engine with Compose 2.24.4+ (the local port override uses `!override`), a DNS hostname, a TLS certificate/private key, the platform currency, a random JWT secret and three distinct URL-safe database passwords. Backup operations additionally need the host Docker CLI, OpenSSH client, cron, local backup storage and a separately administered off-host SSH destination with a retention policy. The smoke script additionally needs Python 3, OpenSSL and ssh-keygen; it builds an SSH-server test image in a disposable Docker context.

Copy `.env.deploy.example` to `.env.deploy`, replace every placeholder and set mode 600. Set `PUBLIC_HOST` to the lowercase hostname without a scheme/port and `PUBLIC_ORIGIN` to its canonical HTTPS origin without a trailing slash. Set `TLS_CERT_DIR` to a host directory containing **actual readable** `fullchain.pem` and `privkey.pem`; a symlink into an unmounted certificate archive will not work. Keep private keys mode 600 and the containing directory private. Certificates/env files/dumps are ignored by Git and excluded from the application build context. Do not put migration credentials in the app environment or expose Docker's API publicly.

For production, provision a certificate trusted by clients using the operator's certificate issuer. Mount the certificate directory read-only. Renew/stage both files atomically, run `nginx -t`, then `nginx -s reload`; monitor expiry. Renewing certificates is an operator responsibility, separate from application migrations.

## Local TLS

From the repository root:

```sh
mkdir -p .certs
chmod 700 .certs
openssl req -x509 -newkey rsa:2048 -nodes -days 7 \
  -subj /CN=localhost -addext subjectAltName=DNS:localhost \
  -keyout .certs/privkey.pem -out .certs/fullchain.pem
chmod 600 .certs/privkey.pem
cp .env.deploy.example .env.deploy
chmod 600 .env.deploy
# Generate/replace secrets and set these local values in .env.deploy:
# PUBLIC_HOST=localhost
# PUBLIC_ORIGIN=https://localhost:8443
# TLS_CERT_DIR=./.certs
docker compose --env-file .env.deploy -p takeaway-local-tls \
  -f docker-compose.yml -f docker-compose.proxy-local.yml up -d --build --wait
curl --cacert .certs/fullchain.pem https://localhost:8443/healthz
curl -I http://localhost:8080/healthz
```

The local override publishes only nginx on loopback 8080/8443 and uses a separate Compose project/volume. Trust the specific generated certificate with `--cacert`; do not disable certificate verification for normal API traffic. Never combine proxy-local, host-development and test overrides.

## Startup, health and shutdown

For production, use only the base Compose file and the configured production env file:

```sh
docker compose --env-file .env.deploy -p takeaway build
docker compose --env-file .env.deploy -p takeaway up -d --wait --wait-timeout 90
docker compose --env-file .env.deploy -p takeaway exec -T nginx nginx -t
curl --fail https://orders.example.com/readyz
docker compose --env-file .env.deploy -p takeaway logs --tail 100 app migrate nginx
docker compose --env-file .env.deploy -p takeaway ps
```

Replace the sample hostname with the configured one. Bootstrap the first admin from an interactive terminal with `docker compose --env-file .env.deploy -p takeaway exec app python -m app.cli create-admin`; enter the password at its hidden prompt, never as a command argument. Inspect failed migrations rather than repeatedly restarting app. The nginx container's healthcheck validates its configuration; `/readyz` through HTTPS verifies the complete proxy/app/database path. `/healthz` verifies process liveness. Monitor readiness separately: Docker's `unless-stopped` policy restarts exited processes, not merely unhealthy containers.

The Compose graph starts db → migrate → app → nginx. Shutdown reverses it; app has 30 seconds to stop, including Uvicorn's 20-second graceful-request timeout. Use `docker compose --env-file .env.deploy -p takeaway down` to stop and remove containers/networks while preserving PostgreSQL data. Never add `-v` to production/development shutdown. To stop serving traffic while retaining containers, stop nginx first and then app.

Database access is limited to its private internal network. App also joins the private proxy network, and nginx alone joins the edge network and publishes ports. `--forwarded-allow-ips=*` is valid only within this trusted single-host boundary. Do not attach untrusted containers to either private network or add app/db port mappings. The edge terminates client TLS directly; no external CDN/load-balancer forwarded-header trust is configured. If adding one later, explicitly restrict its source networks and configure trusted real-IP handling before changing rate-limit identity.

Nginx overwrites X-Forwarded-For/X-Real-IP with the actual connection address, X-Forwarded-Proto with the TLS scheme and X-Request-ID with its generated ID. It preserves the validated Host header/port for upstream redirects. Unknown hostnames are rejected. Client-supplied forwarding chains and request IDs cannot set these values. The same request ID is returned on upstream and proxy-generated errors. Access logs are JSON without URLs/queries/body/authentication/contact fields. Nginx's default request error records can echo private URLs, so error output is limited to critical process errors; use the safe access status/request ID to diagnose request failures.

## Limits and timeouts

| Boundary | Configuration |
| --- | --- |
| POST `/api/v1/auth/token` | Per actual client IP, 5 requests/minute; burst 10 with immediate servicing (`nodelay`), then 429. |
| POST `/api/v1/orders` | Per actual client IP, 10 requests/minute, no extra burst, then 429. Successful requests are not the only ones counted. |
| GET `/api/v1/orders`, active/detail polling, and `/status-changes` | No checkout/login limiter. Method keys are empty for non-POST requests. |
| Request body | 64 KiB maximum; larger bodies return 413. |
| Slow clients/upstream | Header/body timeouts 10s, keepalive 30s, client send 30s; proxy connect 3s and read/send 30s. Request and response buffering enabled. |
| JSON responses | Gzip enabled above 256 bytes, with `Vary: Accept-Encoding`. |

Nginx normalizes paths before exact-location matching; polling and status changes use separate locations from creation. Automatic trailing-slash redirects lead back to the canonical rate-limited endpoint. Proxy-generated 413/429 bodies are nginx responses, outside the app's domain-error JSON contract.

Two app workers × (pool_size 10 + max_overflow 5) allow at most **30 runtime connections**, plus one-shot migrations, probes, backup/restore and operator connections. Do not increase workers/pools without recalculating PostgreSQL's connection budget. App pool checkout timeout is 5s; database connect timeout is 3s.

## Deploying migrations and rollback

Use immutable `APP_IMAGE` tags/digests in the private deployment env file. Take a verified backup first and retain the previous application image. Plan a short maintenance window for migrations that cannot safely coexist with the old app:

```sh
# Update APP_IMAGE to the new immutable release, then build/pull it as appropriate.
docker compose --env-file .env.deploy -p takeaway build
docker compose --env-file .env.deploy -p takeaway stop nginx app
docker compose --env-file .env.deploy -p takeaway up -d --wait db
docker compose --env-file .env.deploy -p takeaway up --no-deps \
  --force-recreate --exit-code-from migrate migrate
# Continue only if the preceding command exits 0.
docker compose --env-file .env.deploy -p takeaway up -d --wait --wait-timeout 90 app nginx
curl --fail https://orders.example.com/readyz
```

Run as separate checked steps; do not continue to startup on a migration error. Explicit recreation reruns even an already completed migrator. Stopping/restarting nginx also refreshes its upstream DNS after app replacement. Inspect migration and startup logs and exercise a safe read through HTTPS before reopening traffic.

Use expand-then-contract schema changes: first add compatible structures, deploy code that tolerates old/new records, perform any needed data migration, and remove old structures only in a later release after old code is retired. This release does not implement unattended rolling migrations/backfill workers. If an expand migration is compatible, rollback may select the previous app image while retaining the schema. Do not blindly run Alembic downgrade after writes or a destructive migration. A database restore is a separate recovery decision with potential loss of writes since the backup; restore into isolation first, verify it, stop writes, and explicitly plan the cutover. Changing env passwords does not rotate existing PostgreSQL roles; coordinate actual role-password rotation and secret updates without discarding the volume.

## Nightly off-host backups

`scripts/backup.sh` uses pg_dump custom format under the migration-owner login already confined to the database container. Passwords are read there, never passed in argv or committed backup configuration. It uses a private local directory, mode-600 archive, overlap lock, partial-file staging and archive validation. It transfers the completed archive using batch SCP with strict host-key checking, then applies local retention **only after transfer succeeds**. A failed off-host copy exits nonzero and preserves older local backups. Alert on any nonzero backup exit or missing daily artifact; cron alone is not a monitoring system. After an untrappable kill or host crash, inspect any remaining `.backup-lock` and remove it only after confirming no backup is active.

Copy `.env.backup.example` to `/etc/takeaway-backup.env`, owned by the backup operator and mode 600. It is trusted shell configuration; values containing spaces require shell quoting. Configure an SSH key and a restricted account on a different machine, dedicated to the backup directory. Pin its host key via a trusted channel. Example `/etc/takeaway-backup.ssh` (mode 600):

```text
Host backup.example.net
    IdentityFile /etc/takeaway-backup_ed25519
    UserKnownHostsFile /etc/takeaway-backup_known_hosts
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
    ConnectTimeout 10
```

The key file is mode 600. Restrict the receiving account to the intended storage/transfer duties; this does not require production database credentials on the backup host. Docker access on the application host is privileged: grant it only to a trusted operator. Verify one manual run and inspect the off-host archive before installing cron:

```sh
set -a
. /etc/takeaway-backup.env
set +a
/opt/takeaway/scripts/backup.sh
```

Install this in the trusted host operator's crontab (02:00 **host time**; set/check that timezone deliberately):

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 2 * * * /bin/sh -c 'set -a; . /etc/takeaway-backup.env; set +a; exec /opt/takeaway/scripts/backup.sh' >> /var/log/takeaway-backup.log 2>&1
```

Configure/rotate the log and monitor it. Default local retention is seven days. On the **backup host**, use a separately controlled retention job for the dedicated directory, for example thirty days:

```cron
15 3 * * * find /srv/takeaway/backups -maxdepth 1 -type f -name 'takeaway-*.dump' -mtime +30 -delete
```

Replace the directory and retention with approved values. The application host does not delete remote backups. Protect backup disks/accounts and encrypted transport; dumps contain personal data and password hashes. This is a nightly recovery point, not continuous/PITR protection. Schedule regular restore drills and verify off-host availability; database backup does not replace preserving operator configuration and TLS material securely.

## Restore drill into a separate database

Fetch a selected archive to a private host directory. The script allows only a new `takeaway_restore_<suffix>` database, rejects existing targets, and never drops or overwrites the live database:

```sh
DEPLOY_ENV_FILE=/opt/takeaway/.env.deploy \
COMPOSE_PROJECT=takeaway RESTORE_DATABASE=takeaway_restore_drill \
  /opt/takeaway/scripts/restore.sh /private/path/takeaway-selected.dump
```

The bootstrap account creates the isolated database with the migration owner, revokes public connection access and restores atomically with `pg_restore --exit-on-error --single-transaction`. Existing owner/runtime role names must exist; for a different cluster, provision those roles first with distinct credentials and the init-role procedure. A failed restore may leave an empty isolated database for inspection; it never alters the source. The runtime account is not granted CONNECT to the restored database by default. Use the owner for inspection, or explicitly grant temporary access only for a controlled drill.

Verify the Alembic revision, counts and values/checksums of orders, order_lines and order_status_changes, including contact/currency/pricing snapshots and chronological actor history. Do not point the live app to a drill database. Compare to a source snapshot captured at backup time rather than a still-changing live source. Remove a drill database only after review; this script deliberately contains no destructive cleanup/cutover operation.

## Reproducible acceptance checks

```sh
docker build -t takeaway-app:local .
python3 scripts/runtime_smoke.py --image takeaway-app:local
python3 scripts/proxy_smoke.py --image takeaway-app:local
sh -n scripts/backup.sh scripts/restore.sh
uv run --locked pytest -W error -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
```

The proxy smoke creates its own certificate, randomly named Compose project and loopback ephemeral nginx ports. It checks nginx syntax, trusted TLS, redirects/forwarded scheme, request IDs, gzip, body limits, actual 429 behavior while polling/status changes remain available, and private app/db ports. It places a sale-priced mock-paid order using real HTTPS registration/login, progresses it, runs the actual backup script through SSH to a separate disposable SSH-server container, compares transferred bytes and verifies failure/success retention. It restores into a new database and checks order/address/currency/price snapshots and history, then rejects live/existing restore targets. All test containers, volumes, keys, certificates and the SSH image are cleaned up. The SSH test models a separate backup machine; the actual production hostname/key/storage/retention and cron installation remain operator inputs.

Implementation references: [nginx request limits and empty keys](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html), [nginx proxy headers/buffering/timeouts](https://nginx.org/en/docs/http/ngx_http_proxy_module.html), [PostgreSQL pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html).
