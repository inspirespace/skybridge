#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="skybridge"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
DISCOVERY_DIR="${DISCOVERY_DIR:-${ROOT_DIR}/data/discovery}"
DISCOVERY_UPLOAD_FILE="${DISCOVERY_UPLOAD_FILE:-}"
HEADFUL="${HEADFUL:-}"

if [ ! -f "${ENV_FILE}" ]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Create one from .env.example and retry." >&2
  exit 1
fi

HEADFUL_ARGS=()
if [ "${HEADFUL}" = "1" ] || [ "${HEADFUL}" = "true" ]; then
  HEADFUL_ARGS+=(--headful)
fi

ARGS=(--discovery-dir "${DISCOVERY_DIR}")
if [ -n "${DISCOVERY_UPLOAD_FILE}" ]; then
  ARGS+=(--discovery-upload-file "${DISCOVERY_UPLOAD_FILE}")
fi

DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}" docker build -t "${IMAGE_NAME}" "${ROOT_DIR}"

exec docker run --rm \
  --name "${IMAGE_NAME}-discovery" \
  --env-file "${ENV_FILE}" \
  -v "${ROOT_DIR}":/app \
  -w /app \
  "${IMAGE_NAME}" \
  python -m src.discovery_cli "${HEADFUL_ARGS[@]}" "${ARGS[@]}" "$@"
