#!/usr/bin/env bash
set -euo pipefail

: "${LOAD_TEST_AUTHORIZED:?Set LOAD_TEST_AUTHORIZED=YES only after the target owner approves this exact test}"
if [[ "$LOAD_TEST_AUTHORIZED" != "YES" ]]; then
  echo "Refusing to run: LOAD_TEST_AUTHORIZED must equal YES." >&2
  exit 2
fi
: "${TARGET_BASE_URL:?Set TARGET_BASE_URL to the authorized local/staging URL}"
case "$TARGET_BASE_URL" in
  http://*|https://*) ;;
  *) echo "TARGET_BASE_URL must begin with http:// or https://" >&2; exit 2;;
esac
if [[ "$TARGET_BASE_URL" == *"@"* ]]; then
  echo "Do not include embedded credentials in TARGET_BASE_URL." >&2
  exit 2
fi

USERS="${USERS:-1}"
SPAWN_RATE="${SPAWN_RATE:-1}"
RUN_TIME="${RUN_TIME:-30s}"
FLOW_PATHS="${FLOW_PATHS:-/,/health}"
[[ "$USERS" =~ ^[0-9]+$ ]] && (( USERS >= 1 && USERS <= 10 )) || { echo "USERS must be 1–10." >&2; exit 2; }
[[ "$SPAWN_RATE" =~ ^[0-9]+$ ]] && (( SPAWN_RATE >= 1 && SPAWN_RATE <= 5 )) || { echo "SPAWN_RATE must be 1–5 users/second." >&2; exit 2; }
if [[ "$RUN_TIME" =~ ^([0-9]+)(s|m)$ ]]; then
  amount="${BASH_REMATCH[1]}"
  unit="${BASH_REMATCH[2]}"
  seconds="$amount"
  [[ "$unit" == "m" ]] && seconds=$((amount * 60))
  (( seconds >= 1 && seconds <= 120 )) || { echo "RUN_TIME must be 1s–120s." >&2; exit 2; }
else
  echo "RUN_TIME must look like 30s or 2m (maximum 120s)." >&2
  exit 2
fi

command -v locust >/dev/null 2>&1 || { echo "Locust is not installed; install locust before running." >&2; exit 127; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export LOAD_TEST_AUTHORIZED TARGET_BASE_URL FLOW_PATHS
exec locust --headless \
  --locustfile "$SCRIPT_DIR/locust/locustfile.py" \
  --host "$TARGET_BASE_URL" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME"
