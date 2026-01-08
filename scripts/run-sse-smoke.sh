#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8001}"
AUTH_MODE="${AUTH_MODE:-header}"
USER_ID="${USER_ID:-smoke-$(date +%s)@skybridge.dev}"

cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]]; then
    kill "${UVICORN_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

AUTH_MODE="${AUTH_MODE}" python -m uvicorn src.backend.app:app --host 127.0.0.1 --port "${PORT}" >/tmp/uvicorn.log 2>&1 &
UVICORN_PID=$!
sleep 2

job_json="$(
  curl -sS -X POST "http://127.0.0.1:${PORT}/jobs" \
    -H "Content-Type: application/json" \
    -H "X-User-Id: ${USER_ID}" \
    -d "{\"credentials\":{\"cloudahoy_username\":\"bad@example.com\",\"cloudahoy_password\":\"bad\",\"flysto_username\":\"bad@example.com\",\"flysto_password\":\"bad\"}}"
)"

job_id="$(printf "%s" "${job_json}" | python -c 'import json,sys; print(json.load(sys.stdin).get("job_id",""))')"
echo "job_id=${job_id}"

curl --max-time 5 -s -N "http://127.0.0.1:${PORT}/jobs/${job_id}/events" \
  -H "Accept: text/event-stream" \
  -H "X-User-Id: ${USER_ID}" \
  | head -n 10
