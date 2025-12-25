#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="${1:-${RUN_ID:-}}"
RUNS_DIR="${RUNS_DIR:-${ROOT_DIR}/data/runs}"
ONLINE_VERIFY="${ONLINE_VERIFY:-0}"

if [[ -z "${RUN_ID}" ]]; then
  echo "Usage: $0 <RUN_ID>" >&2
  exit 2
fi

RUN_DIR="${RUNS_DIR}/${RUN_ID}"
REVIEW_PATH="${RUN_DIR}/review.json"
REPORT_PATH="${RUN_DIR}/import_report.json"
EXPORTS_DIR="${RUN_DIR}/cloudahoy_exports"
LOG_PATH="${RUN_DIR}/docker.log"
STATE_PATH="${RUN_DIR}/migration.db"

python - <<PY
import json
from pathlib import Path
import sys

run_dir = Path("${RUN_DIR}")
review_path = Path("${REVIEW_PATH}")
report_path = Path("${REPORT_PATH}")
exports_dir = Path("${EXPORTS_DIR}")
log_path = Path("${LOG_PATH}")
state_path = Path("${STATE_PATH}")

errors = []

if not run_dir.exists():
    errors.append(f"Missing run dir: {run_dir}")

for path, label in [
    (review_path, "review.json"),
    (report_path, "import_report.json"),
    (log_path, "docker.log"),
    (state_path, "migration.db"),
]:
    if not path.exists():
        errors.append(f"Missing {label}: {path}")

review_items = 0
if review_path.exists():
    try:
        review = json.loads(review_path.read_text())
        review_items = len(review.get("items", []))
    except Exception:
        errors.append("Unable to parse review.json")

report_items = 0
summary = None
if report_path.exists():
    try:
        report = json.loads(report_path.read_text())
        report_items = len(report.get("items", []))
        summary = {
            "attempted": report.get("attempted"),
            "succeeded": report.get("succeeded"),
            "failed": report.get("failed"),
            "pending": report.get("pending"),
            "verification": report.get("verification"),
        }
    except Exception:
        errors.append("Unable to parse import_report.json")

exports_count = 0
if exports_dir.exists():
    exports_count = len([p for p in exports_dir.iterdir() if p.is_file()])

print(f"Run dir: {run_dir}")
print(f"Review items: {review_items}")
print(f"Report items: {report_items}")
print(f"Exports count: {exports_count}")

if summary:
    print("Report summary:", summary)

if review_items and exports_count:
    expected = review_items * 3
    if exports_count != expected:
        errors.append(f"Expected {expected} export files (3 per flight), got {exports_count}")

if report_items and review_items and report_items != review_items:
    errors.append(f"Report items ({report_items}) != review items ({review_items})")

if summary:
    if summary.get("failed") not in (0, None):
        errors.append(f"Report failed != 0 (got {summary.get('failed')})")
    if summary.get("pending") not in (0, None):
        errors.append(f"Report pending != 0 (got {summary.get('pending')})")
    verification = summary.get("verification") or {}
    if verification.get("missing") not in (0, None):
        errors.append(f"Verification missing != 0 (got {verification.get('missing')})")

if errors:
    print("\nIssues:")
    for err in errors:
        print(f"- {err}")
    sys.exit(1)

print("\nLocal verification passed.")
PY

if [[ "${ONLINE_VERIFY}" == "1" ]]; then
  if [[ ! -f "${ROOT_DIR}/.env" ]]; then
    echo "Missing .env for online verification." >&2
    exit 2
  fi
  set -a
  source "${ROOT_DIR}/.env"
  set +a
  python -m src.cli --verify-import-report --import-report "${REPORT_PATH}"
fi
