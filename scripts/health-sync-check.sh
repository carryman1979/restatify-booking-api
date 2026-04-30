#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8088}"
API_KEY="${API_KEY:-}"
TIMEZONE="${TIMEZONE:-Europe/Berlin}"
DURATION_MINUTES="${DURATION_MINUTES:-60}"
WINDOW_DAYS="${WINDOW_DAYS:-7}"
RUN_SYNC_WORKER=0

usage() {
  cat <<'USAGE'
Usage: scripts/health-sync-check.sh [-u API_BASE_URL] [-k API_KEY] [-w]

Options:
  -u  API base URL (default: $API_BASE_URL or http://127.0.0.1:8088)
  -k  API key (default: $API_KEY env var)
  -w  Run python sync worker once before API tests

Environment:
  API_BASE_URL      API base URL, e.g. https://api.restatify.tech
  API_KEY           API key used for authenticated checks
  TIMEZONE          Timezone for slot check payload (default: Europe/Berlin)
  DURATION_MINUTES  Slot duration for slot check (default: 60)
  WINDOW_DAYS       Search window in days for slot check (default: 7)
  CURL_INSECURE     Set to 1 to pass -k to curl (self-signed test envs)
USAGE
}

while getopts ":u:k:wh" opt; do
  case "${opt}" in
    u) API_BASE_URL="${OPTARG}" ;;
    k) API_KEY="${OPTARG}" ;;
    w) RUN_SYNC_WORKER=1 ;;
    h)
      usage
      exit 0
      ;;
    :)
      echo "Missing value for -${OPTARG}" >&2
      usage
      exit 1
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${API_KEY}" ]]; then
  echo "API key missing. Set API_KEY env var or pass -k." >&2
  exit 1
fi

CURL_OPTS=(-sS --max-time 20)
if [[ "${CURL_INSECURE:-0}" == "1" ]]; then
  CURL_OPTS+=(-k)
fi

json_get() {
  local expression="$1"
  python3 - "$expression" <<'PY'
import json
import sys

expr = sys.argv[1]
obj = json.load(sys.stdin)

if expr == "health_status":
    print(str(obj.get("status", "")))
elif expr == "calendar_sources_count":
    val = obj.get("calendar_sources", [])
    print(len(val) if isinstance(val, list) else 0)
elif expr == "slots_count":
    val = obj.get("slots", [])
    print(len(val) if isinstance(val, list) else 0)
else:
    print("")
PY
}

if [[ "${RUN_SYNC_WORKER}" == "1" ]]; then
  echo "[1/4] Running one sync worker pass (python -m app.sync_google_freebusy)"
  python3 -m app.sync_google_freebusy
fi

echo "[2/4] Checking health endpoint"
HEALTH_BODY="$(curl "${CURL_OPTS[@]}" "${API_BASE_URL%/}/health")"
HEALTH_STATUS="$(printf '%s' "${HEALTH_BODY}" | json_get health_status)"
if [[ "${HEALTH_STATUS}" != "ok" ]]; then
  echo "Health check failed. Body: ${HEALTH_BODY}" >&2
  exit 1
fi

echo "[3/4] Checking authenticated sync config"
CONFIG_BODY="$(curl "${CURL_OPTS[@]}" -H "X-API-Key: ${API_KEY}" -H "Accept: application/json" "${API_BASE_URL%/}/v1/config/sync")"
CALENDAR_SOURCES_COUNT="$(printf '%s' "${CONFIG_BODY}" | json_get calendar_sources_count)"
echo "Configured calendar sources: ${CALENDAR_SOURCES_COUNT}"
if [[ "${CALENDAR_SOURCES_COUNT}" -eq 0 ]]; then
  echo "No calendar_sources configured. Booking backend will return unavailable." >&2
  exit 2
fi

echo "[4/4] Checking slots search endpoint"
SLOT_PAYLOAD="$(python3 - <<PY
from datetime import datetime, timedelta, timezone
import json

start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
end = start + timedelta(days=int(${WINDOW_DAYS}))
print(json.dumps({
    "start_iso": start.isoformat(),
    "end_iso": end.isoformat(),
    "duration_minutes": int(${DURATION_MINUTES}),
    "timezone": "${TIMEZONE}",
}))
PY
)"
SLOT_BODY="$(curl "${CURL_OPTS[@]}" -X POST -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" --data "${SLOT_PAYLOAD}" "${API_BASE_URL%/}/v1/slots/search")"
SLOTS_COUNT="$(printf '%s' "${SLOT_BODY}" | json_get slots_count)"

echo "Slots endpoint reachable. Returned slots: ${SLOTS_COUNT}"
echo "Smoke test finished successfully."
