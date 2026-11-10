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

VUS="${VUS:-1}"
DURATION="${DURATION:-30s}"
FLOW_PATHS="${FLOW_PATHS:-/,/health}"
THINK_SECONDS="${THINK_SECONDS:-1}"
[[ "$VUS" =~ ^[0-9]+$ ]] && (( VUS >= 1 && VUS <= 10 )) || { echo "VUS must be 1–10." >&2; exit 2; }
[[ "$THINK_SECONDS" =~ ^[0-9]+$ ]] && (( THINK_SECONDS >= 1 && THINK_SECONDS <= 10 )) || { echo "THINK_SECONDS must be 1–10." >&2; exit 2; }
if [[ "$DURATION" =~ ^([0-9]+)(s|m)$ ]]; then
  amount="${BASH_REMATCH[1]}"
  unit="${BASH_REMATCH[2]}"
  seconds="$amount"
  [[ "$unit" == "m" ]] && seconds=$((amount * 60))
  (( seconds >= 1 && seconds <= 120 )) || { echo "DURATION must be 1s–120s." >&2; exit 2; }
else
  echo "DURATION must look like 30s or 2m (maximum 120s)." >&2
  exit 2
fi

command -v k6 >/dev/null 2>&1 || { echo "k6 is not installed; install k6 before running." >&2; exit 127; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
K6_ARGS=(run)
if [[ -n "${SUMMARY_FILE:-}" ]]; then
  mkdir -p "$(dirname -- "$SUMMARY_FILE")"
  K6_ARGS+=(--summary-export "$SUMMARY_FILE")
fi
K6_ARGS+=(
  --env "LOAD_TEST_AUTHORIZED=$LOAD_TEST_AUTHORIZED"
  --env "TARGET_BASE_URL=$TARGET_BASE_URL"
  --env "APPROVED_TARGET_URL=$APPROVED_TARGET_URL"
  --env "VUS=$VUS"
  --env "DURATION=$DURATION"
  --env "FLOW_PATHS=$FLOW_PATHS"
  --env "THINK_SECONDS=$THINK_SECONDS"
  "$SCRIPT_DIR/k6/user-flow.js"
)
exec k6 "${K6_ARGS[@]}"
