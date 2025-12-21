#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5433}"
HOST="${HOST:-127.0.0.1}"
DBNAME="${DBNAME:-restore_drill}"

latest="$(ls -t backup_*.dump 2>/dev/null | head -n 1)"
: "${latest:?No backup_*.dump found. Run ./db_backup.sh first.}"

echo "Using dump: $latest"

conda run -n pg18 dropdb  -h "$HOST" -p "$PORT" --if-exists "$DBNAME" >/dev/null 2>&1 || true
conda run -n pg18 createdb -h "$HOST" -p "$PORT" "$DBNAME"

conda run -n pg18 pg_restore -h "$HOST" -p "$PORT" -d "$DBNAME" \
  --no-owner --no-privileges \
  --clean --if-exists \
  --verbose \
  "$latest" >/dev/null

conda run -n pg18 psql -h "$HOST" -p "$PORT" -d "$DBNAME" -c "\dt+"
conda run -n pg18 psql -h "$HOST" -p "$PORT" -d "$DBNAME" -c "select count(*) as users_rows from public.users;"
echo "OK restore into running local PG"
