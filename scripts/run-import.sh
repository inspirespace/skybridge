#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
MAX_FLIGHTS="${MAX_FLIGHTS:-}"

if [ -z "${MAX_FLIGHTS}" ] && [ -f "${ENV_FILE}" ]; then
  MAX_FLIGHTS="$(grep -E '^MAX_FLIGHTS=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
fi
MAX_FLIGHTS="${MAX_FLIGHTS:-5}"

exec "${ROOT_DIR}/scripts/run.sh" --mode hybrid --approve-import --max-flights "${MAX_FLIGHTS}"
