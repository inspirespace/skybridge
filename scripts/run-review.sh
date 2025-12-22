#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
MAX_FLIGHTS="${MAX_FLIGHTS:-}"

if [ -z "${MAX_FLIGHTS}" ] && [ -f "${ENV_FILE}" ]; then
  MAX_FLIGHTS="$(grep -E '^MAX_FLIGHTS=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
fi
MAX_FLIGHTS="${MAX_FLIGHTS:-5}"

if [ ! -f "${ENV_FILE}" ]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Create one from .env.example and retry." >&2
  exit 1
fi

exec "${ROOT_DIR}/scripts/run.sh" --review --max-flights "${MAX_FLIGHTS}"
