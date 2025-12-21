#!/usr/bin/env bash
set -euo pipefail

: "${DB_URL:?DB_URL must be set (run: source .env)}"

ts="$(date +%F_%H%M)"
out="backup_${ts}.dump"

conda run -n pg18 psql "$DB_URL" -c "select now();" -v ON_ERROR_STOP=1 >/dev/null
conda run -n pg18 pg_dump "$DB_URL" -Fc --no-owner --no-privileges -f "$out"

echo "Created: $out"
ls -lh "$out"
conda run -n pg18 pg_restore -l "$out" | head -n 25
echo "OK: $out"
