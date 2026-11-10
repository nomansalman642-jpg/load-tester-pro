#!/usr/bin/env bash
set -euo pipefail

: "${LOAD_TEST_AUTHORIZED:?Set LOAD_TEST_AUTHORIZED=YES only after the target owner approves this exact test}"
if [[ "$LOAD_TEST_AUTHORIZED" != "YES" ]]; then
  echo "Refusing to run: LOAD_TEST_AUTHORIZED must equal YES." >&2
  exit 2
fi
: "${TARGET_BASE_URL:?Set TARGET_BASE_URL to the authorized local/staging URL}"
: "${APPROVED_TARGET_URL:?Set APPROVED_TARGET_URL to the exact user-approved URL}"
if [[ "$TARGET_BASE_URL" != "$APPROVED_TARGET_URL" ]]; then
  echo "Refusing to run: TARGET_BASE_URL does not exactly match APPROVED_TARGET_URL." >&2
  exit 2
fi
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
LOCUST_TEMPLATE="${LOCUST_TEMPLATE:-read-only}"
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
case "$LOCUST_TEMPLATE" in
  read-only)
    LOCUSTFILE="$SCRIPT_DIR/locust/locustfile.py"
    ;;
  checkout-auth)
    [[ "${TARGET_ENV:-}" == "local" || "${TARGET_ENV:-}" == "staging" ]] || { echo "Checkout flow requires TARGET_ENV=local or staging." >&2; exit 2; }
    [[ "${ALLOW_TEST_WRITES:-}" == "YES" && "${PAYMENT_TEST_MODE:-}" == "YES" ]] || { echo "Checkout flow requires ALLOW_TEST_WRITES=YES and PAYMENT_TEST_MODE=YES." >&2; exit 2; }
    LOCUSTFILE="$SCRIPT_DIR/locust/checkout_auth_flow.py"
    ;;
  *) echo "LOCUST_TEMPLATE must be read-only or checkout-auth." >&2; exit 2;;
esac
export LOAD_TEST_AUTHORIZED TARGET_BASE_URL APPROVED_TARGET_URL FLOW_PATHS LOCUST_TEMPLATE
exec locust --headless \
  --locustfile "$LOCUSTFILE" \
  --host "$TARGET_BASE_URL" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME"
