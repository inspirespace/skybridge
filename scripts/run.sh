#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="skybridge"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
RUNS_DIR="${RUNS_DIR:-${ROOT_DIR}/data/runs}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${RUNS_DIR}/${RUN_ID}"

if [ ! -f "${ENV_FILE}" ]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Create one from .env.example and retry." >&2
  exit 1
fi

mkdir -p "${RUN_DIR}"

REVIEW_PATH="${REVIEW_PATH:-${RUN_DIR}/review.json}"
IMPORT_REPORT="${IMPORT_REPORT:-${RUN_DIR}/import_report.json}"
EXPORTS_DIR="${EXPORTS_DIR:-${RUN_DIR}/cloudahoy_exports}"
STATE_PATH="${STATE_PATH:-${RUN_DIR}/migration.db}"
LOG_PATH="${LOG_PATH:-${RUN_DIR}/docker.log}"

DOCKER_BUILDKIT=1 docker build -q -t "${IMAGE_NAME}" "${ROOT_DIR}" >/dev/null 2>&1

exec docker run --rm \
  --name "${IMAGE_NAME}" \
  -e RUN_ID="${RUN_ID}" \
  -e REVIEW_PATH="${REVIEW_PATH}" \
  -e IMPORT_REPORT="${IMPORT_REPORT}" \
  -e EXPORTS_DIR="${EXPORTS_DIR}" \
  -e STATE_PATH="${STATE_PATH}" \
  --env-file "${ENV_FILE}" \
  -v "${ROOT_DIR}":/app \
  -w /app \
  "${IMAGE_NAME}" "$@" | tee -a "${LOG_PATH}"
