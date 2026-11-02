#!/bin/sh
# Restore into a NEW explicitly isolated database; never overwrite the live database.
set -eu
: "${DEPLOY_ENV_FILE:?Set the absolute path to the private deployment env file}"
: "${RESTORE_DATABASE:?Set a new database named takeaway_restore_<suffix>}"
COMPOSE_PROJECT=${COMPOSE_PROJECT:-takeaway}
case "$RESTORE_DATABASE" in takeaway_restore_?*) ;; *) echo 'Require takeaway_restore_<suffix>' >&2; exit 1;; esac
case "$RESTORE_DATABASE" in *[!a-z0-9_]*) echo 'Use lowercase letters, digits and underscores' >&2; exit 1;; esac
[ "${#RESTORE_DATABASE}" -le 63 ] || { echo 'Database name exceeds 63 characters' >&2; exit 1; }
[ "$#" -eq 1 ] && [ -f "$1" ] || { echo 'Usage: restore.sh /absolute/backup.dump' >&2; exit 1; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
docker compose --env-file "$DEPLOY_ENV_FILE" -p "$COMPOSE_PROJECT" \
    -f "$ROOT/docker-compose.yml" exec -T db sh -eu -c '
    export PGPASSWORD="$POSTGRES_PASSWORD"
    # createdb fails if the destination exists; no DROP/CLEAN/live-db fallback.
    createdb -h 127.0.0.1 -U "$POSTGRES_USER" -O "$MIGRATION_DB_USER" -T template0 "$1"
    # Identifier input is restricted above to lowercase ASCII/digits/underscore.
    psql -h 127.0.0.1 -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
        -c "REVOKE CONNECT ON DATABASE \"$1\" FROM PUBLIC"
' sh "$RESTORE_DATABASE"
docker compose --env-file "$DEPLOY_ENV_FILE" -p "$COMPOSE_PROJECT" \
    -f "$ROOT/docker-compose.yml" exec -T db sh -eu -c '
    export PGPASSWORD="$POSTGRES_PASSWORD"
    exec pg_restore -h 127.0.0.1 -U "$POSTGRES_USER" -d "$1" \
        --exit-on-error --single-transaction
' sh "$RESTORE_DATABASE" < "$1"
printf 'Restore complete in isolated database: %s\n' "$RESTORE_DATABASE"
