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
  - deletes the Firestore default database (after clearing its data)
  - clears Realtime Database root
  - disables Firebase Hosting sites
  - deletes Cloud Storage buckets in the project after clearing their objects

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

TEMP_CREDENTIALS_FILE=""
GCLOUD_ACCESS_TOKEN_FILE=""
GCLOUD_CONFIG_DIR=""
GCLOUD_CONFIG_DIR_OWNED=0

if ! command -v firebase >/dev/null 2>&1; then
  echo "Firebase CLI is required. Install it first (for example: npm install -g firebase-tools)." >&2
  exit 1
fi

cleanup_credentials() {
  if [ -n "$TEMP_CREDENTIALS_FILE" ] && [ -f "$TEMP_CREDENTIALS_FILE" ]; then
    rm -f "$TEMP_CREDENTIALS_FILE"
  fi
}

cleanup_gcloud_access_token() {
  if [ -n "$GCLOUD_ACCESS_TOKEN_FILE" ] && [ -f "$GCLOUD_ACCESS_TOKEN_FILE" ]; then
    rm -f "$GCLOUD_ACCESS_TOKEN_FILE"
  fi
}

cleanup_gcloud_config_dir() {
  if [ "$GCLOUD_CONFIG_DIR_OWNED" -eq 1 ] && [ -n "$GCLOUD_CONFIG_DIR" ] && [ -d "$GCLOUD_CONFIG_DIR" ]; then
    rm -rf "$GCLOUD_CONFIG_DIR"
  fi
}

cleanup_all() {
  cleanup_credentials
  cleanup_gcloud_access_token
  cleanup_gcloud_config_dir
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

normalize_bucket_candidate() {
  local value
  value="$(normalize_env_value "${1:-}")"
  value="${value#gs://}"
  value="${value%%/*}"
  printf '%s' "$value"
}

ensure_gcloud_config_dir() {
  if [ -n "${CLOUDSDK_CONFIG:-}" ]; then
    GCLOUD_CONFIG_DIR="$CLOUDSDK_CONFIG"
    GCLOUD_CONFIG_DIR_OWNED=0
    return 0
  fi
  if [ -n "$GCLOUD_CONFIG_DIR" ] && [ -d "$GCLOUD_CONFIG_DIR" ]; then
    export CLOUDSDK_CONFIG="$GCLOUD_CONFIG_DIR"
    return 0
  fi
  GCLOUD_CONFIG_DIR="$(mktemp -d)"
  GCLOUD_CONFIG_DIR_OWNED=1
  export CLOUDSDK_CONFIG="$GCLOUD_CONFIG_DIR"
}

run_gcloud() {
  ensure_gcloud_config_dir
  gcloud "$@"
}

bucket_list_contains() {
  local list="$1"
  local candidate="$2"
  if [ -z "$candidate" ]; then
    return 1
  fi
  printf '%s\n' "$list" | grep -Fxq "$candidate"
}

bucket_list_add() {
  local var_name="$1"
  local normalized current
  normalized="$(normalize_bucket_candidate "${2:-}")"
  if [ -z "$normalized" ]; then
    return 0
  fi
  current="${!var_name:-}"
  if bucket_list_contains "$current" "$normalized"; then
    return 0
  fi
  if [ -z "$current" ]; then
    printf -v "$var_name" '%s' "$normalized"
  else
    printf -v "$var_name" '%s\n%s' "$current" "$normalized"
  fi
}

google_access_token() {
  local token
  token="$(
    python3 - <<'PY' 2>/dev/null
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    import google.auth
except Exception:
    Request = None
    service_account = None
    google = None

DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def refresh_authorized_user(data: dict) -> str:
    refresh_token = data.get("refresh_token", "")
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    token_uri = data.get("token_uri") or DEFAULT_TOKEN_URI
    if not refresh_token or not client_id or not client_secret:
        return ""
    payload = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        token_uri,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    return parsed.get("access_token", "")


def refresh_service_account(path: str) -> str:
    if service_account is None or Request is None:
        return ""
    credentials = service_account.Credentials.from_service_account_file(
        path, scopes=SCOPES
    )
    credentials.refresh(Request())
    return getattr(credentials, "token", "") or ""


def try_credentials_file(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return ""

    cred_type = payload.get("type", "")
    try:
        if cred_type == "authorized_user":
            return refresh_authorized_user(payload)
        if cred_type == "service_account":
            return refresh_service_account(str(path))
    except Exception:
        return ""
    return ""


def default_adc_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_config_home:
        return Path(xdg_config_home) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"

credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
for candidate in filter(None, [credentials_path, str(default_adc_path())]):
    token = try_credentials_file(Path(candidate))
    if token:
        print(token)
        sys.exit(0)

if google is None or Request is None:
    sys.exit(1)

try:
    credentials, _ = google.auth.default(scopes=SCOPES)
except Exception:
    sys.exit(1)

try:
    credentials.refresh(Request())
except Exception:
    sys.exit(1)

token = getattr(credentials, "token", "")
if not token:
    sys.exit(1)
print(token)
PY
  )" || true
  if [ -n "$token" ]; then
    printf '%s' "$token"
    return 0
  fi

  if command -v gcloud >/dev/null 2>&1; then
    token="$(
      run_gcloud --quiet auth application-default print-access-token 2>/dev/null
    )" || true
    if [ -n "$token" ]; then
      printf '%s' "$token"
      return 0
    fi
  fi

  token="$(
    node - <<'NODE' 2>/dev/null
const fs = require("fs");
const path = require("path");

const candidates = [];
if (process.env.XDG_CONFIG_HOME) {
  candidates.push(
    path.join(process.env.XDG_CONFIG_HOME, "configstore", "firebase-tools.json")
  );
}
if (process.env.HOME) {
  candidates.push(
    path.join(process.env.HOME, ".config", "configstore", "firebase-tools.json")
  );
  candidates.push(
    path.join(
      process.env.HOME,
      "Library",
      "Preferences",
      "configstore",
      "firebase-tools.json"
    )
  );
}

for (const filePath of candidates) {
  if (!fs.existsSync(filePath)) continue;
  try {
    const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
    const token =
      payload?.tokens?.access_token ||
      payload?.tokens?.accessToken ||
      payload?.user?.tokens?.access_token ||
      payload?.user?.tokens?.accessToken ||
      "";
    const expiresAt = Number(
      payload?.tokens?.expires_at ??
        payload?.user?.tokens?.expires_at ??
        0
    );
    if (!token || typeof token !== "string") continue;
    if (!expiresAt || Number.isNaN(expiresAt) || expiresAt > Date.now() + 60_000) {
      process.stdout.write(token);
      process.exit(0);
    }
    process.stdout.write(token);
    process.exit(0);
  } catch {
    continue;
  }
}
process.exit(1);
NODE
  )" || true
  if [ -n "$token" ]; then
    printf '%s' "$token"
    return 0
  fi

  return 1
}

ensure_gcloud_access_token_file() {
  if [ -n "$GCLOUD_ACCESS_TOKEN_FILE" ] && [ -f "$GCLOUD_ACCESS_TOKEN_FILE" ]; then
    return 0
  fi

  local token
  token="$(google_access_token || true)"
  if [ -z "$token" ]; then
    return 1
  fi

  GCLOUD_ACCESS_TOKEN_FILE="$(mktemp)"
  printf '%s' "$token" > "$GCLOUD_ACCESS_TOKEN_FILE"
}

interactive_bootstrap_adc() {
  if ! command -v gcloud >/dev/null 2>&1; then
    return 1
  fi
  if [ -n "${CI:-}" ] || [ ! -t 0 ] || [ ! -t 1 ]; then
    return 1
  fi

  echo "No Google access token found for Cloud Storage cleanup. Starting Application Default Credentials login..."
  if run_gcloud --project "$PROJECT_ID" auth application-default login; then
    return 0
  fi

  echo "ADC login failed; retrying with --no-launch-browser..."
  run_gcloud --project "$PROJECT_ID" auth application-default login --no-launch-browser
}

storage_bucket_exists() {
  local bucket="$1"
  node - "$bucket" "$GCLOUD_ACCESS_TOKEN_FILE" "$PROJECT_ID" <<'NODE' >/dev/null 2>&1
const fs = require("fs");

const bucket = process.argv[2];
const tokenFile = process.argv[3];
const projectId = process.argv[4];

const token = fs.readFileSync(tokenFile, "utf8").trim();
if (!token || !bucket) {
  process.exit(1);
}

(async () => {
  const response = await fetch(
    `https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(bucket)}?fields=name`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Goog-User-Project": projectId,
      },
    }
  );
  if (response.ok) {
    process.exit(0);
  }
  if (response.status === 404) {
    process.exit(1);
  }
  process.exit(2);
})().catch(() => process.exit(2));
NODE
}

list_project_storage_buckets() {
  node - "$GCLOUD_ACCESS_TOKEN_FILE" "$PROJECT_ID" <<'NODE'
const fs = require("fs");

const tokenFile = process.argv[2];
const projectId = process.argv[3];

const token = fs.readFileSync(tokenFile, "utf8").trim();
if (!token || !projectId) {
  process.exit(1);
}

const headers = {
  Authorization: `Bearer ${token}`,
  "X-Goog-User-Project": projectId,
};

(async () => {
  const buckets = new Set();
  let pageToken = "";
  while (true) {
    const url = new URL("https://storage.googleapis.com/storage/v1/b");
    url.searchParams.set("project", projectId);
    url.searchParams.set("fields", "items(name),nextPageToken");
    url.searchParams.set("maxResults", "1000");
    if (pageToken) {
      url.searchParams.set("pageToken", pageToken);
    }
    const response = await fetch(url, { headers });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Bucket list failed (${response.status}): ${body}`);
    }
    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    for (const item of items) {
      if (typeof item?.name === "string" && item.name.trim()) {
        buckets.add(item.name.trim());
      }
    }
    if (!payload?.nextPageToken) {
      break;
    }
    pageToken = payload.nextPageToken;
  }
  process.stdout.write(Array.from(buckets).join("\n"));
})().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
NODE
}

delete_storage_bucket() {
  local bucket="$1"
  local output status

  if output="$(
    node - "$bucket" "$GCLOUD_ACCESS_TOKEN_FILE" "$PROJECT_ID" <<'NODE' 2>&1
const fs = require("fs");

const bucket = process.argv[2];
const tokenFile = process.argv[3];
const projectId = process.argv[4];

const token = fs.readFileSync(tokenFile, "utf8").trim();
if (!token || !bucket) {
  console.error("Missing storage cleanup token or bucket name.");
  process.exit(2);
}

const headers = {
  Authorization: `Bearer ${token}`,
  "X-Goog-User-Project": projectId,
};

const listObjects = async (pageToken = "") => {
  const url = new URL(`https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(bucket)}/o`);
  url.searchParams.set("versions", "true");
  url.searchParams.set("maxResults", "1000");
  url.searchParams.set("fields", "items(name,generation),nextPageToken");
  if (pageToken) {
    url.searchParams.set("pageToken", pageToken);
  }
  const response = await fetch(url, { headers });
  if (response.status === 404) {
    return { missingBucket: true, items: [], nextPageToken: "" };
  }
  if (!response.ok) {
    throw new Error(`List failed (${response.status})`);
  }
  const payload = await response.json();
  return {
    missingBucket: false,
    items: Array.isArray(payload?.items) ? payload.items : [],
    nextPageToken: payload?.nextPageToken || "",
  };
};

const deleteObject = async (name, generation) => {
  const url = new URL(
    `https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(bucket)}/o/${encodeURIComponent(name)}`
  );
  if (generation) {
    url.searchParams.set("generation", String(generation));
  }
  const response = await fetch(url, {
    method: "DELETE",
    headers,
  });
  if (response.ok || response.status === 404) {
    return;
  }
  const body = await response.text();
  throw new Error(`Delete failed for ${name}#${generation || "live"} (${response.status}): ${body}`);
};

const deleteBucket = async () => {
  const url = new URL(`https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(bucket)}`);
  const response = await fetch(url, {
    method: "DELETE",
    headers,
  });
  if (response.ok || response.status === 404) {
    return response.status;
  }
  const body = await response.text();
  throw new Error(`Bucket delete failed (${response.status}): ${body}`);
};

(async () => {
  const objects = [];
  let pageToken = "";
  while (true) {
    const page = await listObjects(pageToken);
    if (page.missingBucket) {
      process.exit(11);
    }
    objects.push(...page.items);
    if (!page.nextPageToken) {
      break;
    }
    pageToken = page.nextPageToken;
  }

  if (objects.length === 0) {
    const bucketDeleteStatus = await deleteBucket();
    if (bucketDeleteStatus === 404) {
      process.exit(11);
    }
    console.log(`Deleted empty bucket ${bucket}.`);
    process.exit(0);
  }

  for (const object of objects) {
    await deleteObject(object?.name || "", object?.generation || "");
  }

  await deleteBucket();
  console.log(`Deleted ${objects.length} object version(s) and bucket ${bucket}.`);
})().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(2);
});
NODE
  )"; then
    status=0
  else
    status=$?
  fi

  case "$status" in
    0)
      [ -n "$output" ] && printf '%s\n' "$output"
      return 0
      return 0
      ;;
    11)
      return 1
      ;;
    *)
      [ -n "$output" ] && printf '%s\n' "$output" >&2
      echo "Warning: deleting storage bucket ${bucket} failed; continuing." >&2
      return 0
      ;;
  esac
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

clear_firestore_data() {
  local output
  if output="$(firebase firestore:delete --project "$PROJECT_ID" --database "(default)" --all-collections --force 2>&1)"; then
    [ -n "$output" ] && printf '%s\n' "$output"
    return 0
  fi

  if printf '%s' "$output" | grep -Eiq 'Unable to list collection IDs|database .* does not exist|NOT_FOUND'; then
    echo "  - no Firestore collections found (or default database not initialized); skipping."
    return 0
  fi

  printf '%s\n' "$output" >&2
  echo "Warning: clearing Firestore data failed; continuing." >&2
  return 0
}

delete_firestore_database() {
  local output
  if output="$(firebase firestore:databases:delete "(default)" --project "$PROJECT_ID" --force 2>&1)"; then
    [ -n "$output" ] && printf '%s\n' "$output"
    return 0
  fi

  if printf '%s' "$output" | grep -Eiq 'database .* does not exist|NOT_FOUND|No databases found'; then
    echo "  - no Firestore default database found; skipping delete."
    return 0
  fi

  printf '%s\n' "$output" >&2
  echo "Warning: deleting Firestore default database failed; continuing." >&2
  return 0
}

clear_realtime_database_root() {
  local output
  if output="$(firebase database:remove / --project "$PROJECT_ID" --force --disable-triggers 2>&1)"; then
    [ -n "$output" ] && printf '%s\n' "$output"
    return 0
  fi

  if printf '%s' "$output" | grep -Eiq "haven't created a Realtime Database instance|default Realtime Database instance"; then
    echo "  - no Realtime Database instance found; skipping."
    return 0
  fi

  printf '%s\n' "$output" >&2
  echo "Warning: clearing Realtime Database data failed; continuing." >&2
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
clear_firestore_data

echo "Deleting Firestore default database..."
delete_firestore_database

echo "Clearing Realtime Database root..."
clear_realtime_database_root

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

echo "Deleting Firebase Storage buckets..."
if ! ensure_gcloud_access_token_file; then
  interactive_bootstrap_adc || true
  if ! ensure_gcloud_access_token_file; then
    echo "Warning: could not acquire a Google access token for Cloud Storage bucket deletion; continuing." >&2
  else
    storage_buckets="$(list_project_storage_buckets 2>/dev/null || true)"
    if [ -z "$storage_buckets" ]; then
      echo "  - no project storage buckets found"
      storage_buckets=""
    fi
    found_storage_bucket=0
    while IFS= read -r bucket; do
      [ -n "$bucket" ] || continue
      if storage_bucket_exists "$bucket"; then
        :
      else
        status=$?
        if [ "$status" -eq 1 ]; then
          continue
        fi
        echo "Warning: could not verify storage bucket ${bucket}; continuing." >&2
        continue
      fi
      found_storage_bucket=1
      echo "  - deleting storage bucket: $bucket"
      delete_storage_bucket "$bucket"
    done <<EOF
$storage_buckets
EOF
    if [ -n "$storage_buckets" ] && [ "$found_storage_bucket" -eq 0 ]; then
      echo "  - no accessible project storage buckets matched"
    fi
  fi
else
  storage_buckets="$(list_project_storage_buckets 2>/dev/null || true)"
  if [ -z "$storage_buckets" ]; then
    echo "  - no project storage buckets found"
    storage_buckets=""
  fi
  found_storage_bucket=0
  while IFS= read -r bucket; do
    [ -n "$bucket" ] || continue
    if storage_bucket_exists "$bucket"; then
      :
    else
      status=$?
      if [ "$status" -eq 1 ]; then
        continue
      fi
      echo "Warning: could not verify storage bucket ${bucket}; continuing." >&2
      continue
    fi
    found_storage_bucket=1
    echo "  - deleting storage bucket: $bucket"
    delete_storage_bucket "$bucket"
  done <<EOF
$storage_buckets
EOF
  if [ -n "$storage_buckets" ] && [ "$found_storage_bucket" -eq 0 ]; then
    echo "  - no accessible project storage buckets matched"
  fi
fi

cat <<EOF
Firebase resource clear finished for project: ${PROJECT_ID}

Note:
- Firebase Auth users are not removed by this script.
- Cloud Storage usage metrics can lag, and bucket protection settings (for example soft delete or retention policies) can delay or block full bucket removal.
EOF
