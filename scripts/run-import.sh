#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
MAX_FLIGHTS="${MAX_FLIGHTS:-}"

if [ -z "${MAX_FLIGHTS}" ] && [ -f "${ENV_FILE}" ]; then
  MAX_FLIGHTS="$(grep -E '^MAX_FLIGHTS=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
fi
MAX_FLIGHTS="${MAX_FLIGHTS:-5}"

REVIEW_PATH="${REVIEW_PATH:-${ROOT_DIR}/data/review.json}"
REVIEW_PATH_CONTAINER="data/review.json"
if [ ! -f "${REVIEW_PATH}" ]; then
  echo "Missing review manifest: ${REVIEW_PATH}" >&2
  echo "Run ./scripts/run-review.sh first." >&2
  exit 1
fi
REVIEW_ID="$(python -c "import json; from pathlib import Path; path=Path('${REVIEW_PATH}'); data=json.loads(path.read_text()); print(data.get('review_id',''))")"
if [ -z "${REVIEW_ID}" ]; then
  echo "Review ID not found in ${REVIEW_PATH}" >&2
  exit 1
fi

exec "${ROOT_DIR}/scripts/run.sh" --approve-import --review-path "${REVIEW_PATH_CONTAINER}" --review-id "${REVIEW_ID}" --max-flights "${MAX_FLIGHTS}"
