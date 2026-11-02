#!/bin/sh
# Host cron entry point. Credentials are read only by Compose/the database container.
set -eu
umask 077
: "${DEPLOY_ENV_FILE:?Set the absolute path to the private deployment env file}"
: "${BACKUP_DIR:?Set the absolute local backup directory}"
: "${BACKUP_REMOTE:?Set user@backup-host:/absolute/dedicated/path}"
COMPOSE_PROJECT=${COMPOSE_PROJECT:-takeaway}
LOCAL_KEEP_DAYS=${LOCAL_KEEP_DAYS:-7}
case "$LOCAL_KEEP_DAYS" in ''|*[!0-9]*) echo 'LOCAL_KEEP_DAYS must be an integer' >&2; exit 1;; esac
case "$DEPLOY_ENV_FILE:$BACKUP_DIR" in /*:/*) ;; *) echo 'Use absolute env/backup paths' >&2; exit 1;; esac
case "$BACKUP_REMOTE" in *@*:/*) ;; *) echo 'BACKUP_REMOTE must be user@host:/absolute/path' >&2; exit 1;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
lock="$BACKUP_DIR/.backup-lock"
if ! mkdir "$lock" 2>/dev/null; then echo 'Another backup holds the lock' >&2; exit 1; fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
file="$BACKUP_DIR/takeaway-$stamp-$$.dump"
partial="$file.partial"
trap 'rm -f "$partial"; rmdir "$lock"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
# Passwords stay out of argv. The owner can read all domain tables/history.
docker compose --env-file "$DEPLOY_ENV_FILE" -p "$COMPOSE_PROJECT" \
    -f "$ROOT/docker-compose.yml" exec -T db sh -eu -c '
    export PGPASSWORD="$MIGRATION_DB_PASSWORD"
    exec pg_dump -h 127.0.0.1 -U "$MIGRATION_DB_USER" -d "$POSTGRES_DB" --format=custom
' > "$partial"
# Validate the archive directory before promoting/transferring the backup.
docker compose --env-file "$DEPLOY_ENV_FILE" -p "$COMPOSE_PROJECT" \
    -f "$ROOT/docker-compose.yml" exec -T db pg_restore --list < "$partial" > /dev/null
mv "$partial" "$file"
# Dedicated backup-host account; batch SSH must already have a trusted host key.
if [ -n "${BACKUP_SSH_CONFIG:-}" ]; then set -- -F "$BACKUP_SSH_CONFIG"; else set --; fi
scp "$@" -B -o StrictHostKeyChecking=yes "$file" "$BACKUP_REMOTE/"
# Local retention only after a successful off-host copy. Remote retention is run
# on the backup host; see docs/deployment-operations.md.
find "$BACKUP_DIR" -type f -name 'takeaway-*.dump' -mtime +"$LOCAL_KEEP_DAYS" -delete
printf 'Backup complete: %s\n' "$(basename "$file")"
