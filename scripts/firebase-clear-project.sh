#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FIREBASE_CONFIG_SCRIPT="${FIREBASE_CONFIG_SCRIPT:-scripts/firebase-config.sh}"

usage() {
  cat <<'EOF'
Usage: ./scripts/firebase-clear-project.sh [--project <firebase_project_id>] [--region <region>] [--force]

Clears Firebase resources while keeping the project itself:
  - deletes all Cloud Functions
  - clears Firestore default database data
  - clears Realtime Database root
  - disables Firebase Hosting sites

Defaults are read from .firebaserc via scripts/firebase-config.sh.
EOF
}

PROJECT_ID="${FIREBASE_PROJECT_ID:-$(sh "$FIREBASE_CONFIG_SCRIPT" project 2>/dev/null || true)}"
REGION="${FIREBASE_REGION:-$(sh "$FIREBASE_CONFIG_SCRIPT" region 2>/dev/null || true)}"
FORCE=0

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
    --region)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --region." >&2
        usage
        exit 1
      fi
      REGION="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
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
  echo "Firebase project id is required. Set FIREBASE_PROJECT_ID or .firebaserc projects.default." >&2
  exit 1
fi

if [ -z "$REGION" ]; then
  REGION="europe-west1"
fi

export FIREBASE_PROJECT_ID="$PROJECT_ID"
export FIREBASE_REGION="$REGION"

if ! command -v firebase >/dev/null 2>&1; then
  echo "Firebase CLI is required. Install it first (for example: npm install -g firebase-tools)." >&2
  exit 1
fi

has_firebase_auth() {
  firebase projects:list --json >/dev/null 2>&1
}

if ! has_firebase_auth; then
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
Firebase authentication is required before clearing project resources.

Use one of:
  1) Interactive login:
     firebase login --reauth
     # if browser callback fails:
     firebase login --reauth --no-localhost
  2) Service account credentials:
     export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/firebase-service-account.json
EOF
  exit 1
fi

if [ "$FORCE" -ne 1 ]; then
  echo "This will clear Firebase resources for project '${PROJECT_ID}' (region hint: ${REGION}) without deleting the project."
  echo "Type the project id to confirm:"
  read -r confirmation
  if [ "$confirmation" != "$PROJECT_ID" ]; then
    echo "Confirmation mismatch. Aborting."
    exit 1
  fi
fi

best_effort() {
  local description="$1"
  shift
  if "$@"; then
    return 0
  fi
  echo "Warning: ${description} failed; continuing." >&2
  return 0
}

list_function_ids() {
  local raw
  if ! raw="$(firebase --project "$PROJECT_ID" --json functions:list 2>/dev/null || true)"; then
    return 0
  fi
  node -e '
const fs = require("fs");
const text = fs.readFileSync(0, "utf8").trim();
if (!text) process.exit(0);

let data;
try {
  data = JSON.parse(text);
} catch {
  process.exit(0);
}

const rows =
  (Array.isArray(data?.result) && data.result) ||
  (Array.isArray(data?.result?.functions) && data.result.functions) ||
  (Array.isArray(data?.functions) && data.functions) ||
  [];

const ids = [...new Set(rows.map((fn) => fn?.id || fn?.name?.split("/").pop()).filter(Boolean))];
if (ids.length > 0) {
  process.stdout.write(ids.join("\n"));
}
' <<< "$raw"
}

list_hosting_sites() {
  local raw
  if ! raw="$(firebase --project "$PROJECT_ID" --json hosting:sites:list 2>/dev/null || true)"; then
    return 0
  fi
  node -e '
const fs = require("fs");
const text = fs.readFileSync(0, "utf8").trim();
if (!text) process.exit(0);

let data;
try {
  data = JSON.parse(text);
} catch {
  process.exit(0);
}

const rows =
  (Array.isArray(data?.result) && data.result) ||
  (Array.isArray(data?.result?.sites) && data.result.sites) ||
  (Array.isArray(data?.sites) && data.sites) ||
  [];

const ids = [...new Set(rows.map((site) => site?.name?.split("/").pop() || site?.siteId).filter(Boolean))];
if (ids.length > 0) {
  process.stdout.write(ids.join("\n"));
}
' <<< "$raw"
}

echo "Clearing Cloud Functions..."
function_ids="$(list_function_ids || true)"
if [ -n "$function_ids" ]; then
  while IFS= read -r function_id; do
    [ -n "$function_id" ] || continue
    echo "  - deleting function: $function_id"
    best_effort "deleting function ${function_id}" firebase functions:delete "$function_id" --project "$PROJECT_ID" --force
  done <<EOF
$function_ids
EOF
else
  echo "  - no deployed functions found"
fi

echo "Clearing Firestore default database data..."
best_effort \
  "clearing Firestore data" \
  firebase firestore:delete --project "$PROJECT_ID" --database "(default)" --all-collections --force

echo "Clearing Realtime Database root..."
best_effort \
  "clearing Realtime Database data" \
  firebase database:remove / --project "$PROJECT_ID" --force --disable-triggers

echo "Disabling Firebase Hosting sites..."
site_ids="$(list_hosting_sites || true)"
if [ -n "$site_ids" ]; then
  while IFS= read -r site_id; do
    [ -n "$site_id" ] || continue
    echo "  - disabling hosting site: $site_id"
    best_effort "disabling hosting site ${site_id}" firebase hosting:disable --project "$PROJECT_ID" --site "$site_id" --force
  done <<EOF
$site_ids
EOF
else
  best_effort "disabling default hosting site" firebase hosting:disable --project "$PROJECT_ID" --force
fi

cat <<EOF
Firebase resource clear finished for project: ${PROJECT_ID}

Note:
- Firebase Auth users and Cloud Storage objects are not removed by Firebase CLI in this script.
  Clear them in Firebase Console if you need a fully empty runtime state.
EOF
