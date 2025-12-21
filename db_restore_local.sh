#!/usr/bin/env bash
set -euo pipefail

latest="$(ls -t backup_*.dump 2>/dev/null | head -n 1)"
: "${latest:?No backup_*.dump found. Run ./db_backup.sh first.}"

PGDATA="${PGDATA:-$(pwd)/.pgdata_restore}"
PORT="${PORT:-5433}"
DBNAME="${DBNAME:-restore_drill}"

mkdir -p "$PGDATA"
grep -q '^\.pgdata_restore$' .gitignore 2>/dev/null || echo ".pgdata_restore" >> .gitignore

# initdb once
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  conda run -n pg18 initdb -D "$PGDATA" --auth=trust
fi

# start server
conda run -n pg18 pg_ctl -D "$PGDATA" -l pg_restore_drill.log -o "-p $PORT -h 127.0.0.1" start >/dev/null

cleanup() {
  conda run -n pg18 pg_ctl -D "$PGDATA" stop -m fast >/dev/null 2>&1 || true
}
trap cleanup EXIT

# fresh DB
conda run -n pg18 dropdb -p "$PORT" --if-exists "$DBNAME" >/dev/null 2>&1 || true
conda run -n pg18 createdb -p "$PORT" "$DBNAME"

# restore
conda run -n pg18 pg_restore -p "$PORT" -d "$DBNAME"   --no-owner --no-privileges   --clean --if-exists   --verbose   "$latest" >/dev/null

# verify (edit these checks as your schema grows)
echo "Restored dump: $latest"
conda run -n pg18 psql -p "$PORT" -d "$DBNAME" -c "\dt+"
conda run -n pg18 psql -p "$PORT" -d "$DBNAME" -c "select count(*) as users_rows from public.users;"
echo "OK local restore drill"
