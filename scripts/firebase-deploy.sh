#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FIREBASE_CONFIG_SCRIPT="${FIREBASE_CONFIG_SCRIPT:-scripts/firebase-config.sh}"

usage() {
  cat <<'EOF'
Usage: ./scripts/firebase-deploy.sh [--project <firebase_project_id>]

Deploys Firebase Functions + Hosting using a shared local/CI workflow.

Options:
  --project <id>  Firebase project id (overrides FIREBASE_PROJECT_ID).
  -h, --help      Show this help message.
EOF
}

PROJECT_ID="${FIREBASE_PROJECT_ID:-$(sh "$FIREBASE_CONFIG_SCRIPT" project 2>/dev/null || true)}"

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

if [ -z "$PROJECT_ID" ]; then
  echo "Firebase project id is required. Set FIREBASE_PROJECT_ID or pass --project <id>." >&2
  exit 1
fi

# Canonical project id wiring: one descriptor in FIREBASE_PROJECT_ID.
export FIREBASE_PROJECT_ID="$PROJECT_ID"

if ! command -v firebase >/dev/null 2>&1; then
  echo "Firebase CLI is required. Install it first (for example: npm install -g firebase-tools)." >&2
  exit 1
fi

FUNCTIONS_REGION="$(sh "$FIREBASE_CONFIG_SCRIPT" region 2>/dev/null || true)"
if [ -z "$FUNCTIONS_REGION" ]; then
  echo "Firebase region is required. Set FIREBASE_REGION or add config.region in .firebaserc." >&2
  exit 1
fi
export FIREBASE_REGION="$FUNCTIONS_REGION"

TEMP_CREDENTIALS_FILE=""
FUNCTIONS_SRC_DIR="functions/src"
FUNCTIONS_SRC_BACKUP_DIR=""
FUNCTIONS_SRC_STAGED=0
FIREBASE_JSON_PATH="firebase.json"
FIREBASE_JSON_BACKUP_FILE=""
FIREBASE_JSON_STAGED=0

cleanup_credentials() {
  if [ -n "$TEMP_CREDENTIALS_FILE" ] && [ -f "$TEMP_CREDENTIALS_FILE" ]; then
    rm -f "$TEMP_CREDENTIALS_FILE"
  fi
}

cleanup_staged_functions_src() {
  if [ "$FUNCTIONS_SRC_STAGED" -ne 1 ]; then
    return
  fi
  if [ -n "$FUNCTIONS_SRC_BACKUP_DIR" ] && [ -d "$FUNCTIONS_SRC_BACKUP_DIR/original_src" ]; then
    rm -rf "$FUNCTIONS_SRC_DIR"
    mv "$FUNCTIONS_SRC_BACKUP_DIR/original_src" "$FUNCTIONS_SRC_DIR"
    rm -rf "$FUNCTIONS_SRC_BACKUP_DIR"
    return
  fi
  rm -rf "$FUNCTIONS_SRC_DIR"
}

cleanup_staged_firebase_json() {
  if [ "$FIREBASE_JSON_STAGED" -ne 1 ]; then
    return
  fi
  if [ -n "$FIREBASE_JSON_BACKUP_FILE" ] && [ -f "$FIREBASE_JSON_BACKUP_FILE" ]; then
    mv "$FIREBASE_JSON_BACKUP_FILE" "$FIREBASE_JSON_PATH"
  fi
}

cleanup_all() {
  cleanup_credentials
  cleanup_staged_functions_src
  cleanup_staged_firebase_json
}
trap cleanup_all EXIT

stage_functions_src() {
  if [ -d "$FUNCTIONS_SRC_DIR" ]; then
    FUNCTIONS_SRC_BACKUP_DIR="$(mktemp -d)"
    mv "$FUNCTIONS_SRC_DIR" "$FUNCTIONS_SRC_BACKUP_DIR/original_src"
  fi
  mkdir -p "$FUNCTIONS_SRC_DIR"
  cp -R src/backend "$FUNCTIONS_SRC_DIR/backend"
  cp -R src/core "$FUNCTIONS_SRC_DIR/core"
  find "$FUNCTIONS_SRC_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +
  FUNCTIONS_SRC_STAGED=1
}

stage_firebase_hosting_region() {
  if [ ! -f "$FIREBASE_JSON_PATH" ]; then
    return
  fi
  FIREBASE_JSON_BACKUP_FILE="$(mktemp)"
  cp "$FIREBASE_JSON_PATH" "$FIREBASE_JSON_BACKUP_FILE"
  node - "$FIREBASE_JSON_PATH" "$FUNCTIONS_REGION" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
const region = process.argv[3];
const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
const rewrites = data?.hosting?.rewrites;
if (!Array.isArray(rewrites)) {
  throw new Error("firebase.json missing hosting.rewrites array");
}
let updated = false;
for (const rewrite of rewrites) {
  if (rewrite?.source === "/api/**") {
    rewrite.function = {
      functionId: "api",
      region,
    };
    delete rewrite.run;
    updated = true;
  }
}
if (!updated) {
  rewrites.unshift({
    source: "/api/**",
    function: {
      functionId: "api",
      region,
    },
  });
}
fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`);
NODE
  FIREBASE_JSON_STAGED=1
}

has_firebase_auth() {
  firebase projects:list --json >/dev/null 2>&1
}

# Allow local runs to reuse the CI auth model by passing FIREBASE_SERVICE_ACCOUNT
# as JSON content. If GOOGLE_APPLICATION_CREDENTIALS is already set, keep it.
if [ -n "${FIREBASE_SERVICE_ACCOUNT:-}" ] && [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  TEMP_CREDENTIALS_FILE="$(mktemp)"
  printf '%s' "$FIREBASE_SERVICE_ACCOUNT" > "$TEMP_CREDENTIALS_FILE"
  export GOOGLE_APPLICATION_CREDENTIALS="$TEMP_CREDENTIALS_FILE"
fi

if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "GOOGLE_APPLICATION_CREDENTIALS points to a missing file: $GOOGLE_APPLICATION_CREDENTIALS" >&2
  exit 1
fi

# Fail fast on auth before any dependency installs/build steps.
if ! has_firebase_auth; then
  # VS Code tasks run with an interactive terminal; attempt login there.
  if [ -z "${CI:-}" ] && [ -t 0 ] && [ -t 1 ]; then
    echo "No Firebase auth found. Starting interactive login..."
    if ! firebase login --reauth; then
      echo "Firebase login failed; retrying with --no-localhost..."
      firebase login --reauth --no-localhost
    fi
  fi
fi

if ! has_firebase_auth; then
  cat >&2 <<'EOF'
Firebase authentication is required before deploy.

Use one of:
  1) Interactive login (local / VS Code task):
     firebase login --reauth
     # if browser callback fails:
     firebase login --reauth --no-localhost
  2) Service account credentials:
     export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/firebase-service-account.json
     # or export FIREBASE_SERVICE_ACCOUNT='<full JSON content>'
EOF
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

echo "Aligning Firebase Hosting rewrite region in firebase.json..."
stage_firebase_hosting_region

echo "Staging shared runtime modules into functions source..."
stage_functions_src

echo "Preparing functions virtual environment with ${PYTHON_BIN}..."
rm -rf functions/venv
"$PYTHON_BIN" -m venv functions/venv
functions/venv/bin/python -m pip install --upgrade pip
functions/venv/bin/python -m pip install -r functions/requirements.txt

deploy_once() {
  firebase deploy --only functions,hosting --project "$PROJECT_ID"
}

echo "Deploying Firebase functions + hosting to project: ${PROJECT_ID} (region: ${FUNCTIONS_REGION})"
if ! deploy_once; then
  echo "Initial deploy failed. Waiting for API/service identity propagation, then retrying once..."
  sleep 20
  deploy_once
fi
