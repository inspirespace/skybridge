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
if [ ! -f "${REVIEW_PATH}" ]; then
  echo "Missing review manifest: ${REVIEW_PATH}" >&2
  echo "Run ./scripts/run-review.sh first." >&2
  exit 1
fi
REVIEW_ID="$(python - <<'PY'\nimport json\nfrom pathlib import Path\npath = Path(\"${REVIEW_PATH}\")\ntry:\n    data = json.loads(path.read_text())\nexcept Exception:\n    print(\"\")\nelse:\n    print(data.get(\"review_id\", \"\"))\nPY\n)"
if [ -z "${REVIEW_ID}" ]; then
  echo "Review ID not found in ${REVIEW_PATH}" >&2
  exit 1
fi

exec "${ROOT_DIR}/scripts/run.sh" --mode hybrid --approve-import --review-path "${REVIEW_PATH}" --review-id "${REVIEW_ID}" --max-flights "${MAX_FLIGHTS}"
