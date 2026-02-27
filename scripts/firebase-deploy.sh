#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FIREBASE_CONFIG_SCRIPT="${FIREBASE_CONFIG_SCRIPT:-scripts/firebase-config.sh}"
FRONTEND_INSTALL_SCRIPT="${FRONTEND_INSTALL_SCRIPT:-scripts/npm-ci-frontend.sh}"

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

if [ ! -x "$FRONTEND_INSTALL_SCRIPT" ]; then
  echo "Frontend install script is missing or not executable: $FRONTEND_INSTALL_SCRIPT" >&2
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
DEPLOY_OUTPUT_FILE=""

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
  if [ -n "$DEPLOY_OUTPUT_FILE" ] && [ -f "$DEPLOY_OUTPUT_FILE" ]; then
    rm -f "$DEPLOY_OUTPUT_FILE"
  fi
}
trap cleanup_all EXIT

normalize_env_value() {
  local raw="$1"
  raw="${raw#"${raw%%[![:space:]]*}"}"
  raw="${raw%"${raw##*[![:space:]]}"}"
  if [[ "$raw" == \"*\" ]] && [[ "$raw" == *\" ]]; then
    raw="${raw:1:${#raw}-2}"
  elif [[ "$raw" == \'*\' ]] && [[ "$raw" == *\' ]]; then
    raw="${raw:1:${#raw}-2}"
  fi
  printf '%s' "$raw"
}

read_env_file_value() {
  local file_path="$1"
  local key="$2"
  [ -f "$file_path" ] || return 1
  local line
  line="$(
    awk -v key="$key" '
      /^[[:space:]]*#/ { next }
      /^[[:space:]]*$/ { next }
      {
        current=$0
        sub(/^[[:space:]]*/, "", current)
        sub(/^export[[:space:]]+/, "", current)
        if (index(current, key "=") != 1) {
          next
        }
        print substr(current, length(key) + 2)
        exit
      }
    ' "$file_path"
  )"
  [ -n "$line" ] || return 1
  normalize_env_value "$line"
}

resolve_config_value() {
  local key="$1"
  shift
  local value="${!key:-}"
  if [ -n "$value" ]; then
    normalize_env_value "$value"
    return 0
  fi

  local file_path
  for file_path in "$@"; do
    value="$(read_env_file_value "$file_path" "$key" || true)"
    if [ -n "$value" ]; then
      printf '%s' "$value"
      return 0
    fi
  done
  return 1
}

is_truthy_value() {
  local value
  value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

preflight_app_check_config() {
  local enforce_value
  enforce_value="$(resolve_config_value APP_CHECK_ENFORCE functions/.env .env || true)"
  if ! is_truthy_value "$enforce_value"; then
    return 0
  fi

  local app_check_enabled
  local app_check_site_key
  app_check_enabled="$(resolve_config_value VITE_FIREBASE_APP_CHECK_ENABLED src/frontend/.env .env || true)"
  app_check_site_key="$(resolve_config_value VITE_FIREBASE_APP_CHECK_SITE_KEY src/frontend/.env .env || true)"

  local -a missing_items=()
  if ! is_truthy_value "$app_check_enabled"; then
    missing_items+=("VITE_FIREBASE_APP_CHECK_ENABLED=1")
  fi
  if [ -z "$app_check_site_key" ]; then
    missing_items+=("VITE_FIREBASE_APP_CHECK_SITE_KEY")
  fi

  if [ "${#missing_items[@]}" -gt 0 ]; then
    echo "App Check preflight: APP_CHECK_ENFORCE is enabled, but frontend App Check config is incomplete." >&2
    echo "Missing/invalid: ${missing_items[*]}" >&2
    echo "Set these via environment variables or in .env before deploy." >&2
    if [ -n "${CI:-}" ]; then
      echo "Failing in CI because requests would be rejected with missing App Check tokens." >&2
      exit 1
    fi
    echo "Warning: continuing local deploy; API requests may fail with 401 App Check errors." >&2
  fi

  local project_number
  project_number="$(resolve_config_value FIREBASE_PROJECT_NUMBER functions/.env .env || true)"
  if [ -z "$project_number" ]; then
    echo "App Check preflight: FIREBASE_PROJECT_NUMBER is not set; backend will attempt runtime lookup." >&2
    echo "Set FIREBASE_PROJECT_NUMBER for deterministic App Check verification configuration." >&2
  fi
}

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

run_firebase_deploy() {
  local output_file="$1"
  set +e
  firebase deploy --only functions,hosting --project "$PROJECT_ID" 2>&1 | tee "$output_file"
  local status="${PIPESTATUS[0]}"
  set -e
  return "$status"
}

delete_trigger_mismatch_functions() {
  local output_file="$1"
  local found=1
  while IFS= read -r line; do
    if [[ "$line" == Error:\ [* ]] && [[ "$line" == *"Changing from an HTTPS function to a background triggered function is not allowed."* ]]; then
      local descriptor="${line#Error: [}"
      descriptor="${descriptor%%]*}"
      local function_name="${descriptor%%(*}"
      local region_name="${descriptor#*(}"
      region_name="${region_name%)}"
      if [ -z "$function_name" ] || [ -z "$region_name" ] || [ "$function_name" = "$descriptor" ]; then
        continue
      fi
      echo "Detected trigger migration conflict for ${function_name}(${region_name}); deleting old function before retry..."
      firebase functions:delete "$function_name" --region "$region_name" --project "$PROJECT_ID" --force
      found=0
    fi
  done < "$output_file"
  return "$found"
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

preflight_app_check_config

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
"$FRONTEND_INSTALL_SCRIPT"

echo "Building frontend..."
npm --prefix src/frontend run build

echo "Running frontend runtime smoke test..."
npm --prefix src/frontend run test:runtime-smoke

echo "Aligning Firebase Hosting rewrite region in firebase.json..."
stage_firebase_hosting_region

echo "Staging shared runtime modules into functions source..."
stage_functions_src

echo "Preparing functions virtual environment with ${PYTHON_BIN}..."
rm -rf functions/venv
"$PYTHON_BIN" -m venv functions/venv
functions/venv/bin/python -m pip install --upgrade pip
functions/venv/bin/python -m pip install -r functions/requirements.txt

DEPLOY_OUTPUT_FILE="$(mktemp)"

echo "Deploying Firebase functions + hosting to project: ${PROJECT_ID} (region: ${FUNCTIONS_REGION})"
if ! run_firebase_deploy "$DEPLOY_OUTPUT_FILE"; then
  if delete_trigger_mismatch_functions "$DEPLOY_OUTPUT_FILE"; then
    echo "Deleted conflicting function definitions. Retrying deploy..."
    run_firebase_deploy "$DEPLOY_OUTPUT_FILE"
    exit 0
  fi
  echo "Initial deploy failed. Waiting for API/service identity propagation, then retrying once..."
  sleep 20
  run_firebase_deploy "$DEPLOY_OUTPUT_FILE"
fi
