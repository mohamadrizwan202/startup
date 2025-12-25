#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://startup-hmwd.onrender.com}"
: "${DBCHECK_TOKEN:?Set DBCHECK_TOKEN in your shell (export DBCHECK_TOKEN=...)}"

curl -fsS -H "Authorization: Bearer ${DBCHECK_TOKEN}" "${BASE}/dbcheck"
echo
