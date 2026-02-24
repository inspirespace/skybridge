#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: ./scripts/firebase-deploy.sh [--project <firebase_project_id>]

Deploys Firebase Functions + Hosting using a shared local/CI workflow.

Options:
  --project <id>  Firebase project id (overrides FIREBASE_PROJECT_ID).
  -h, --help      Show this help message.
EOF
}

PROJECT_ID="${FIREBASE_PROJECT_ID:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --project." >&2
        usage
        exit 1
      fi
      PROJECT_ID="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "$PROJECT_ID" ] && [ -f ".firebaserc" ]; then
  PROJECT_ID="$(sed -n 's/.*"default"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' .firebaserc | head -n 1)"
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Firebase project id is required. Set FIREBASE_PROJECT_ID or pass --project <id>." >&2
  exit 1
fi

if ! command -v firebase >/dev/null 2>&1; then
  echo "Firebase CLI is required. Install it first (for example: npm install -g firebase-tools)." >&2
  exit 1
fi

PYTHON_BIN=""
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Python 3 is required for Firebase Functions dependency preparation." >&2
  exit 1
fi

echo "Preparing frontend dependencies..."
npm --prefix src/frontend ci

echo "Building frontend..."
npm --prefix src/frontend run build

echo "Preparing functions virtual environment with ${PYTHON_BIN}..."
rm -rf functions/venv
"$PYTHON_BIN" -m venv functions/venv
functions/venv/bin/python -m pip install --upgrade pip
functions/venv/bin/python -m pip install -r functions/requirements.txt

echo "Deploying Firebase functions + hosting to project: ${PROJECT_ID}"
firebase deploy --only functions,hosting --project "$PROJECT_ID"
