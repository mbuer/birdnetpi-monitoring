#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo ./deploy/birdnet-pi/verify.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_ENV="/etc/birdnet-monitoring/runtime.env"
RUNTIME_USER="${BIRDNET_RUNTIME_USER:-${SUDO_USER:-}}"
failures=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }
warn() { printf 'WARN  %s\n' "$1"; }

check_active() {
  local unit="$1"
  if systemctl is-active --quiet "$unit"; then pass "$unit active"; else fail "$unit not active"; fi
}

check_enabled() {
  local unit="$1"
  if systemctl is-enabled --quiet "$unit"; then pass "$unit enabled"; else fail "$unit not enabled"; fi
}

if [[ -f "$RUNTIME_ENV" ]]; then
  pass "runtime environment exists"
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
else
  fail "runtime environment missing"
fi

if [[ -n "$RUNTIME_USER" ]] && getent passwd "$RUNTIME_USER" >/dev/null; then
  USER_HOME="$(getent passwd "$RUNTIME_USER" | cut -d: -f6)"
  SQLITE_DB="${BIRDNET_SQLITE_DB:-$USER_HOME/BirdNET-Pi/scripts/birds.db}"
  [[ -r "$SQLITE_DB" ]] && pass "BirdNET SQLite readable" || fail "BirdNET SQLite not readable: $SQLITE_DB"
else
  fail "BirdNET runtime user unresolved"
fi

python3 -c 'import requests, psycopg' >/dev/null 2>&1   && pass "Python collector dependencies" || fail "Python collector dependencies"

if python3 - <<'PY'
import os, psycopg
with psycopg.connect(
    host=os.environ["BIRDNET_DB_HOST"],
    dbname=os.environ["BIRDNET_DB_NAME"],
    user=os.environ["BIRDNET_DB_USER"],
    password=os.environ["BIRDNET_DB_PASSWORD"],
    connect_timeout=5,
) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
PY
then pass "PostgreSQL reachable"; else fail "PostgreSQL unreachable"; fi

if curl -fsS "${BIRDNET_LOKI_URL%/}/ready" >/dev/null; then
  pass "Loki ready"
else
  fail "Loki not ready"
fi

check_active weather.service
check_active alloy.service
check_active birdnet-db-sync.timer
check_enabled birdnet-db-sync.timer
check_active birdnet-forecast.timer
check_enabled birdnet-forecast.timer

if cmp -s "$ROOT/alloy/config.alloy" /etc/alloy/config.alloy; then
  pass "Alloy live config matches Git"
else
  fail "Alloy live config differs from Git"
fi

bird_count="$(curl -fsG "${BIRDNET_LOKI_URL%/}/loki/api/v1/query"   --data-urlencode 'query=sum(count_over_time({unit="birdnet_analysis.service"}[5m]))'   2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("data",{}).get("result",[]); print(r[0]["value"][1] if r else "0")'   || echo 0)"
weather_count="$(curl -fsG "${BIRDNET_LOKI_URL%/}/loki/api/v1/query"   --data-urlencode 'query=sum(count_over_time({job="weather"}[20m]))'   2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("data",{}).get("result",[]); print(r[0]["value"][1] if r else "0")'   || echo 0)"

python3 - "$bird_count" <<'PY' && pass "Recent BirdNET logs in Loki" || warn "No recent BirdNET logs in Loki yet"
import sys
raise SystemExit(0 if float(sys.argv[1]) > 0 else 1)
PY

python3 - "$weather_count" <<'PY' && pass "Recent weather logs in Loki" || warn "No recent weather logs in Loki yet"
import sys
raise SystemExit(0 if float(sys.argv[1]) > 0 else 1)
PY

echo
if (( failures > 0 )); then
  echo "Verification failed: $failures check(s)."
  exit 1
fi
echo "BirdNET Pi verification passed."
