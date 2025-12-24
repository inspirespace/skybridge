#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="skybridge"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [ ! -f "${ENV_FILE}" ]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Create one from .env.example and retry." >&2
  exit 1
fi

DOCKER_BUILDKIT=1 docker build -q -t "${IMAGE_NAME}" "${ROOT_DIR}" >/dev/null 2>&1

exec docker run --rm \
  --name "${IMAGE_NAME}" \
  --env-file "${ENV_FILE}" \
  -v "${ROOT_DIR}":/app \
  -w /app \
  "${IMAGE_NAME}" "$@"
