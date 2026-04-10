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

require_deploy_toolchain() {
  local -a required_tools=("firebase" "npm" "node" "curl" "awk" "sed" "grep" "find")
  local -a missing_tools=()
  local tool
  for tool in "${required_tools[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing_tools+=("$tool")
    fi
  done
  if [ "${#missing_tools[@]}" -eq 0 ]; then
    return 0
  fi
  echo "Firebase deploy preflight: required tools are missing from the current environment." >&2
  printf 'Missing tools: %s\n' "${missing_tools[*]}" >&2
  echo "Run deploy from the configured devcontainer (or install these tools there)." >&2
  exit 1
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

require_deploy_toolchain

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
FUNCTIONS_SRC_DIR="functions/_deploy_src/src"
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

read_env_file_values() {
  local file_path="$1"
  local key="$2"
  [ -f "$file_path" ] || return 1
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
    }
  ' "$file_path" | while IFS= read -r line; do
    line="$(normalize_env_value "$line")"
    [ -z "$line" ] && continue
    printf '%s\n' "$line"
  done
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

normalize_domain_candidate() {
  local value
  value="$(normalize_env_value "${1:-}")"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  value="${value#http://}"
  value="${value#https://}"
  value="${value%%/*}"
  value="${value%%:*}"
  value="${value#[}"
  value="${value%]}"
  printf '%s' "$value"
}

domain_list_contains() {
  local list="$1"
  local candidate="$2"
  if [ -z "$candidate" ]; then
    return 1
  fi
  printf '%s\n' "$list" | grep -Fxq "$candidate"
}

domain_list_add() {
  local var_name="$1"
  local raw_value="$2"
  local normalized current
  normalized="$(normalize_domain_candidate "$raw_value")"
  if [ -z "$normalized" ]; then
    return 0
  fi
  current="${!var_name:-}"
  if domain_list_contains "$current" "$normalized"; then
    return 0
  fi
  if [ -z "$current" ]; then
    printf -v "$var_name" '%s' "$normalized"
  else
    printf -v "$var_name" '%s\n%s' "$current" "$normalized"
  fi
}

split_domain_values() {
  local raw="$1"
  printf '%s' "$raw" | tr ',;' '\n' | while IFS= read -r line || [ -n "$line" ]; do
    line="$(normalize_env_value "$line")"
    [ -z "$line" ] && continue
    for token in $line; do
      printf '%s\n' "$token"
    done
  done
}

collect_authorized_domains_config() {
  local merged=""
  local raw=""
  local candidate=""
  local file_path

  raw="$(normalize_env_value "${FIREBASE_AUTHORIZED_DOMAINS:-}")"
  if [ -n "$raw" ]; then
    while IFS= read -r candidate; do
      [ -z "$candidate" ] && continue
      domain_list_add merged "$candidate"
    done < <(split_domain_values "$raw")
  fi

  for file_path in functions/.env .env; do
    while IFS= read -r raw; do
      [ -z "$raw" ] && continue
      while IFS= read -r candidate; do
        [ -z "$candidate" ] && continue
        domain_list_add merged "$candidate"
      done < <(split_domain_values "$raw")
    done < <(read_env_file_values "$file_path" FIREBASE_AUTHORIZED_DOMAINS || true)
  done

  printf '%s' "$merged"
}

google_access_token() {
  local token
  token="$(
    python3 - <<'PY' 2>/dev/null
import os
import sys

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    import google.auth
except Exception:
    sys.exit(1)

scopes = ["https://www.googleapis.com/auth/cloud-platform"]
credentials = None
credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

if credentials_path and os.path.isfile(credentials_path):
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
else:
    try:
        credentials, _ = google.auth.default(scopes=scopes)
    except Exception:
        sys.exit(1)

if credentials is None:
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
    // Token may still be valid even if local expiry metadata is stale.
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

get_identity_platform_config() {
  local token="$1"
  local output_file="$2"
  curl -fsS \
    -H "Authorization: Bearer ${token}" \
    "https://identitytoolkit.googleapis.com/admin/v2/projects/${PROJECT_ID}/config" \
    >"$output_file"
}

extract_authorized_domains() {
  local file_path="$1"
  node - "$file_path" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
let parsed;
try {
  parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
} catch {
  process.exit(1);
}

const domains = Array.isArray(parsed?.authorizedDomains)
  ? parsed.authorizedDomains
  : Array.isArray(parsed?.authorized_domains)
    ? parsed.authorized_domains
    : [];

for (const value of domains) {
  if (typeof value !== "string") continue;
  const normalized = value.trim().toLowerCase();
  if (!normalized) continue;
  process.stdout.write(`${normalized}\n`);
}
NODE
}

discover_hosting_domains() {
  local token="$1"
  local project_id="$2"
  node - "$token" "$project_id" <<'NODE'
const token = process.argv[2];
const projectId = process.argv[3];

const headers = { Authorization: `Bearer ${token}` };
const domains = new Set();

const addDomain = (value) => {
  if (typeof value !== "string") return;
  let normalized = value.trim().toLowerCase();
  if (!normalized) return;
  try {
    if (normalized.startsWith("http://") || normalized.startsWith("https://")) {
      normalized = new URL(normalized).hostname.toLowerCase();
    }
  } catch {
    // Keep raw value fallback below.
  }
  normalized = normalized.replace(/\/.*$/, "").replace(/:\d+$/, "");
  if (!normalized) return;
  domains.add(normalized);
};

const fetchJson = async (url) => {
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(String(response.status));
  }
  return response.json();
};

(async () => {
  try {
    const sitesPayload = await fetchJson(
      `https://firebasehosting.googleapis.com/v1beta1/projects/${encodeURIComponent(projectId)}/sites`
    );
    const sites = Array.isArray(sitesPayload?.sites) ? sitesPayload.sites : [];
    for (const site of sites) {
      addDomain(site?.defaultUrl);
      if (typeof site?.name !== "string" || !site.name) continue;
      try {
        const customPayload = await fetchJson(
          `https://firebasehosting.googleapis.com/v1beta1/${site.name}/customDomains`
        );
        const customDomains = Array.isArray(customPayload?.customDomains)
          ? customPayload.customDomains
          : [];
        for (const entry of customDomains) {
          addDomain(entry?.domainName);
          if (typeof entry?.name === "string") {
            const marker = "/customDomains/";
            const markerIndex = entry.name.lastIndexOf(marker);
            if (markerIndex >= 0) {
              addDomain(entry.name.slice(markerIndex + marker.length));
            }
          }
        }
      } catch {
        // Best-effort: keep deploy flow resilient when custom domain listing is unavailable.
      }
    }
  } catch {
    // Best-effort: no-op when Hosting API cannot be queried.
  }

  for (const domain of domains) {
    process.stdout.write(`${domain}\n`);
  }
})();
NODE
}

extract_email_signin_flags() {
  local file_path="$1"
  node - "$file_path" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
let parsed;
try {
  parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
} catch {
  process.exit(1);
}

const signIn = parsed?.signIn ?? parsed?.sign_in ?? {};
const email = signIn?.email ?? {};
const enabled = email?.enabled === true ? "1" : "0";
const passwordRequired =
  email?.passwordRequired === true || email?.password_required === true ? "1" : "0";

process.stdout.write(`EMAIL_ENABLED=${enabled}\n`);
process.stdout.write(`EMAIL_PASSWORD_REQUIRED=${passwordRequired}\n`);
NODE
}

read_email_signin_flags() {
  local file_path="$1"
  local email_enabled=""
  local email_password_required=""
  while IFS='=' read -r key value; do
    case "$key" in
      EMAIL_ENABLED) email_enabled="$value" ;;
      EMAIL_PASSWORD_REQUIRED) email_password_required="$value" ;;
    esac
  done < <(extract_email_signin_flags "$file_path")
  printf '%s,%s' "$email_enabled" "$email_password_required"
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

print_firebase_auth_setup_overview() {
  local use_emulator
  use_emulator="$(resolve_config_value VITE_FIREBASE_USE_EMULATOR src/frontend/.env .env || true)"
  if is_truthy_value "$use_emulator"; then
    return 0
  fi

  local app_name project_for_domains auth_domain explicit_domains
  app_name="$(resolve_config_value FIREBASE_AUTH_EMAIL_APP_NAME functions/.env .env || true)"
  if [ -z "$app_name" ]; then
    app_name="Skybridge"
  fi
  app_name="$(normalize_env_value "$app_name")"
  if [ -z "$app_name" ]; then
    app_name="Skybridge"
  fi

  project_for_domains="${VITE_FIREBASE_PROJECT_ID:-${PROJECT_ID}}"
  auth_domain="${VITE_FIREBASE_AUTH_DOMAIN:-${project_for_domains}.firebaseapp.com}"
  explicit_domains="$(collect_authorized_domains_config || true)"

  cat >&2 <<EOF
Firebase Auth manual setup overview for project ${project_for_domains}:
  1) Sign-in method (required):
     - Enable "Email/Password"
     - Enable "Email link (passwordless sign-in)"
     - Console: https://console.firebase.google.com/project/${PROJECT_ID}/authentication/providers
  2) Email template branding + sender domain:
     - Open the "Email address sign-in" template in Firebase Console
     - Prerequisite: enable Google sign-in provider to unlock "Public-facing name"
     - Set sender/app display name to "${app_name}" (or your preferred friendly name)
     - Update subject/body copy so emails say your brand instead of project ids
     - Recommended for production: click "Customize domain" and verify a dedicated sender subdomain
     - Add the exact DNS records Firebase shows at your DNS provider (typically TXT + DKIM CNAME records)
     - Wait for Firebase verification to complete; Console notes this can take up to 48 hours
     - Console: https://console.firebase.google.com/project/${PROJECT_ID}/authentication/templates
  3) Authorized domains for email-link continueUrl (required):
     - Ensure these are present in Authentication -> Settings:
       - ${auth_domain}
       - ${project_for_domains}.web.app
     - Console: https://console.firebase.google.com/project/${PROJECT_ID}/authentication/settings
EOF

  if [ -n "$explicit_domains" ]; then
    echo "  - Additional domains from FIREBASE_AUTHORIZED_DOMAINS (merged env + functions/.env + .env):" >&2
    while IFS= read -r domain; do
      domain="$(normalize_domain_candidate "$domain")"
      [ -z "$domain" ] && continue
      echo "    - $domain" >&2
    done < <(printf '%s\n' "$explicit_domains")
  fi

  echo "Deploy preflight verifies sign-in mode and authorized domains only; it does not auto-patch Firebase Auth templates or project naming." >&2
}

preflight_firebase_auth_signin_config() {
  local use_emulator
  use_emulator="$(resolve_config_value VITE_FIREBASE_USE_EMULATOR src/frontend/.env .env || true)"
  if is_truthy_value "$use_emulator"; then
    return 0
  fi

  local require_email_link
  require_email_link="$(resolve_config_value FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN functions/.env .env || true)"
  if [ -z "$require_email_link" ]; then
    require_email_link="1"
  fi
  if ! is_truthy_value "$require_email_link"; then
    return 0
  fi

  local token
  token="$(google_access_token || true)"
  if [ -z "$token" ]; then
    cat >&2 <<'EOF'
Firebase Auth preflight: could not acquire Google access token to verify sign-in provider configuration.
Checked:
  - Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS / ADC)
  - Firebase CLI local login token cache (~/.config/configstore/firebase-tools.json)
EOF
    if [ -n "${CI:-}" ]; then
      echo "Failing in CI because Firebase Auth provider checks are required." >&2
      exit 1
    fi
    echo "Warning: continuing local deploy without automated provider verification." >&2
    return 0
  fi

  local config_file
  config_file="$(mktemp)"
  local flags
  local email_enabled=""
  local password_required=""
  if ! get_identity_platform_config "$token" "$config_file"; then
    rm -f "$config_file"
    echo "Failed to fetch Firebase Auth config from Identity Toolkit API." >&2
    if [ -n "${CI:-}" ]; then
      exit 1
    fi
    echo "Warning: continuing local deploy without automated provider verification." >&2
    return 0
  fi

  flags="$(read_email_signin_flags "$config_file")"
  email_enabled="${flags%%,*}"
  password_required="${flags#*,}"

  local ok=0
  if [ "$email_enabled" = "1" ] && [ "$password_required" = "0" ]; then
    ok=1
  fi

  if [ "$ok" -ne 1 ]; then
    # Manual provider changes can take a few seconds to propagate; retry briefly.
    local retry=1
    while [ "$retry" -le 5 ]; do
      sleep 2
      if get_identity_platform_config "$token" "$config_file"; then
        flags="$(read_email_signin_flags "$config_file")"
        email_enabled="${flags%%,*}"
        password_required="${flags#*,}"
        if [ "$email_enabled" = "1" ] && [ "$password_required" = "0" ]; then
          ok=1
          break
        fi
      fi
      retry=$((retry + 1))
    done
  fi

  rm -f "$config_file"

  if [ "$ok" -ne 1 ]; then
    local observed_enabled observed_password_required
    observed_enabled="${email_enabled:-<unset>}"
    observed_password_required="${password_required:-<unset>}"
    cat >&2 <<EOF
Firebase Auth preflight failed for project ${PROJECT_ID}.
Expected sign-in config:
  - signIn.email.enabled = true
  - signIn.email.passwordRequired = false (email link sign-in enabled)

Observed via Identity Toolkit API:
  - signIn.email.enabled = ${observed_enabled}
  - signIn.email.passwordRequired = ${observed_password_required}

Fix options:
  1) Firebase Console -> Authentication -> Sign-in method:
     - Enable "Email/Password"
     - Enable "Email link (passwordless sign-in)"
  2) Re-run deploy after the setting is saved.
EOF
    exit 1
  fi
}

first_web_app_id_from_json() {
  local file_path="$1"
  node - "$file_path" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
let data;
try {
  data = JSON.parse(fs.readFileSync(filePath, "utf8"));
} catch {
  process.exit(0);
}

const normalizeAppId = (value) => {
  if (typeof value !== "string") return "";
  if (value.includes("/webApps/")) {
    const parts = value.split("/");
    return parts[parts.length - 1] || "";
  }
  return value;
};

const looksLikeWebAppId = (value) =>
  typeof value === "string" && value.includes(":web:");

const queue = [data];
while (queue.length > 0) {
  const current = queue.shift();
  if (!current) continue;
  if (Array.isArray(current)) {
    for (const item of current) queue.push(item);
    continue;
  }
  if (typeof current !== "object") continue;

  const platform = typeof current.platform === "string" ? current.platform.toUpperCase() : "";
  const candidateKeys = ["appId", "appID", "app_id", "id", "name"];
  if (platform === "WEB") {
    for (const key of candidateKeys) {
      const raw = current[key];
      const appId = normalizeAppId(raw);
      if (looksLikeWebAppId(appId)) {
        process.stdout.write(appId);
        process.exit(0);
      }
    }
  }

  for (const key of candidateKeys) {
    const raw = current[key];
    const appId = normalizeAppId(raw);
    if (looksLikeWebAppId(appId)) {
      process.stdout.write(appId);
      process.exit(0);
    }
  }

  for (const value of Object.values(current)) {
    queue.push(value);
  }
}
NODE
}

first_web_app_id_from_text() {
  local file_path="$1"
  node - "$file_path" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
let raw = "";
try {
  raw = fs.readFileSync(filePath, "utf8");
} catch {
  process.exit(0);
}

const appIdPattern = /\b\d+:\d+:web:[A-Za-z0-9]+\b/g;
const matches = raw.match(appIdPattern);
if (matches && matches.length > 0) {
  process.stdout.write(matches[0]);
}
NODE
}

extract_sdk_config_values() {
  local file_path="$1"
  node - "$file_path" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
const raw = fs.readFileSync(filePath, "utf8");

let apiKey = "";
let appId = "";
let authDomain = "";
let projectId = "";

const parseFromObject = (obj) => {
  if (!obj || typeof obj !== "object") return false;
  const key = obj.apiKey ?? obj.api_key ?? "";
  const app = obj.appId ?? obj.app_id ?? "";
  if (typeof key === "string" && key && typeof app === "string" && app) {
    apiKey = key;
    appId = app;
    authDomain =
      (typeof obj.authDomain === "string" && obj.authDomain) ||
      (typeof obj.auth_domain === "string" && obj.auth_domain) ||
      "";
    projectId =
      (typeof obj.projectId === "string" && obj.projectId) ||
      (typeof obj.project_id === "string" && obj.project_id) ||
      "";
    return true;
  }
  return false;
};

try {
  const parsed = JSON.parse(raw);
  const queue = [parsed];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) continue;
    if (Array.isArray(current)) {
      for (const item of current) queue.push(item);
      continue;
    }
    if (parseFromObject(current)) break;
    if (typeof current === "object") {
      for (const value of Object.values(current)) queue.push(value);
    }
  }
} catch {
  // Fall back to regex-based parsing for non-JSON firebase CLI output.
}

if (!apiKey) {
  const match = raw.match(/apiKey["']?\s*[:=]\s*["']([^"']+)["']/);
  if (match) apiKey = match[1];
}
if (!appId) {
  const match = raw.match(/appId["']?\s*[:=]\s*["']([^"']+)["']/);
  if (match) appId = match[1];
}
if (!authDomain) {
  const match = raw.match(/authDomain["']?\s*[:=]\s*["']([^"']+)["']/);
  if (match) authDomain = match[1];
}
if (!projectId) {
  const match = raw.match(/projectId["']?\s*[:=]\s*["']([^"']+)["']/);
  if (match) projectId = match[1];
}

if (apiKey) process.stdout.write(`VITE_FIREBASE_API_KEY=${apiKey}\n`);
if (appId) process.stdout.write(`VITE_FIREBASE_APP_ID=${appId}\n`);
if (authDomain) process.stdout.write(`VITE_FIREBASE_AUTH_DOMAIN=${authDomain}\n`);
if (projectId) process.stdout.write(`VITE_FIREBASE_PROJECT_ID=${projectId}\n`);
NODE
}

preflight_frontend_firebase_config() {
  local use_emulator
  use_emulator="$(resolve_config_value VITE_FIREBASE_USE_EMULATOR src/frontend/.env .env || true)"
  if is_truthy_value "$use_emulator"; then
    return 0
  fi

  local api_key
  local app_id
  local project_id
  local auth_domain
  local explicit_web_app_id
  api_key="$(resolve_config_value VITE_FIREBASE_API_KEY src/frontend/.env .env || true)"
  app_id="$(resolve_config_value VITE_FIREBASE_APP_ID src/frontend/.env .env || true)"
  project_id="$(resolve_config_value VITE_FIREBASE_PROJECT_ID src/frontend/.env .env || true)"
  auth_domain="$(resolve_config_value VITE_FIREBASE_AUTH_DOMAIN src/frontend/.env .env || true)"
  explicit_web_app_id="$(resolve_config_value FIREBASE_WEB_APP_ID src/frontend/.env .env || true)"

  if [ -z "$project_id" ]; then
    project_id="$PROJECT_ID"
  fi
  if [ -z "$auth_domain" ] && [ -n "$project_id" ]; then
    auth_domain="${project_id}.firebaseapp.com"
  fi

  if [ -z "$api_key" ] || [ -z "$app_id" ]; then
    echo "Frontend Firebase config missing (api key/app id). Attempting to resolve from Firebase web app..." >&2
    local apps_json_file
    local apps_text_file
    local create_json_file
    local create_text_file
    local sdk_config_file
    local apps_err_file
    local resolved_app_id
    apps_json_file="$(mktemp)"
    apps_text_file="$(mktemp)"
    create_json_file="$(mktemp)"
    create_text_file="$(mktemp)"
    sdk_config_file="$(mktemp)"
    apps_err_file="$(mktemp)"
    resolved_app_id=""

    if [ -n "$explicit_web_app_id" ]; then
      resolved_app_id="$explicit_web_app_id"
    fi

    if [ -z "$resolved_app_id" ] && firebase apps:list --project "$PROJECT_ID" --json >"$apps_json_file" 2>"$apps_err_file"; then
      resolved_app_id="$(first_web_app_id_from_json "$apps_json_file" || true)"
    fi

    if [ -z "$resolved_app_id" ] && [ -s "$apps_json_file" ]; then
      resolved_app_id="$(first_web_app_id_from_text "$apps_json_file" || true)"
    fi

    if [ -z "$resolved_app_id" ] && firebase apps:list WEB --project "$PROJECT_ID" >"$apps_text_file" 2>>"$apps_err_file"; then
      resolved_app_id="$(first_web_app_id_from_text "$apps_text_file" || true)"
    fi

    if [ -z "$resolved_app_id" ] && [ -n "$app_id" ]; then
      resolved_app_id="$app_id"
    fi

    if [ -z "$resolved_app_id" ]; then
      echo "No Firebase WEB app found in project ${PROJECT_ID}; creating one for frontend auth..." >&2
      if firebase apps:create WEB "${PROJECT_ID}-web" --project "$PROJECT_ID" --json >"$create_json_file" 2>>"$apps_err_file"; then
        resolved_app_id="$(first_web_app_id_from_json "$create_json_file" || true)"
      fi

      if [ -z "$resolved_app_id" ] && [ -s "$create_json_file" ]; then
        resolved_app_id="$(first_web_app_id_from_text "$create_json_file" || true)"
      fi

      if [ -z "$resolved_app_id" ] && firebase apps:list WEB --project "$PROJECT_ID" >"$apps_text_file" 2>>"$apps_err_file"; then
        resolved_app_id="$(first_web_app_id_from_text "$apps_text_file" || true)"
      fi

      if [ -z "$resolved_app_id" ] && firebase apps:create WEB "${PROJECT_ID}-web" --project "$PROJECT_ID" >"$create_text_file" 2>>"$apps_err_file"; then
        resolved_app_id="$(first_web_app_id_from_text "$create_text_file" || true)"
      fi
    fi

    if [ -n "$resolved_app_id" ] && firebase apps:sdkconfig WEB "$resolved_app_id" --project "$PROJECT_ID" >"$sdk_config_file" 2>>"$apps_err_file"; then
        while IFS='=' read -r key value; do
          case "$key" in
            VITE_FIREBASE_API_KEY)
              [ -z "$api_key" ] && api_key="$value"
              ;;
            VITE_FIREBASE_APP_ID)
              [ -z "$app_id" ] && app_id="$value"
              ;;
            VITE_FIREBASE_AUTH_DOMAIN)
              [ -z "$auth_domain" ] && auth_domain="$value"
              ;;
            VITE_FIREBASE_PROJECT_ID)
              [ -z "$project_id" ] && project_id="$value"
              ;;
          esac
        done < <(extract_sdk_config_values "$sdk_config_file")
    fi

    if [ -z "$api_key" ] || [ -z "$app_id" ]; then
      if [ -n "$resolved_app_id" ]; then
        echo "Resolved Firebase WEB app id: $resolved_app_id (sdk config still missing apiKey/appId)." >&2
      fi
      if [ -s "$apps_err_file" ]; then
        echo "Firebase WEB app resolution diagnostics:" >&2
        sed 's/^/  /' "$apps_err_file" >&2
      fi
    fi

    rm -f "$apps_json_file" "$apps_text_file" "$create_json_file" "$create_text_file" "$sdk_config_file" "$apps_err_file"
  fi

  if [ -z "$api_key" ] || [ -z "$app_id" ] || [ -z "$project_id" ]; then
    cat >&2 <<'EOF'
Frontend Firebase config is incomplete for production Firebase auth.
Required:
  - VITE_FIREBASE_API_KEY
  - VITE_FIREBASE_APP_ID
  - VITE_FIREBASE_PROJECT_ID (or .firebaserc projects.default)

Set these in environment/.env, or ensure the Firebase project has at least one WEB app
so the deploy script can auto-resolve sdk config via Firebase CLI.
EOF
    exit 1
  fi

  export VITE_FIREBASE_API_KEY="$api_key"
  export VITE_FIREBASE_APP_ID="$app_id"
  export VITE_FIREBASE_PROJECT_ID="$project_id"
  if [ -n "$auth_domain" ]; then
    export VITE_FIREBASE_AUTH_DOMAIN="$auth_domain"
  fi
}

preflight_firebase_auth_authorized_domains() {
  local use_emulator
  use_emulator="$(resolve_config_value VITE_FIREBASE_USE_EMULATOR src/frontend/.env .env || true)"
  if is_truthy_value "$use_emulator"; then
    return 0
  fi

  local require_authorized_domains
  require_authorized_domains="$(resolve_config_value FIREBASE_REQUIRE_AUTHORIZED_DOMAINS functions/.env .env || true)"
  if [ -z "$require_authorized_domains" ]; then
    require_authorized_domains="1"
  fi

  local token
  token="$(google_access_token || true)"
  if [ -z "$token" ]; then
    cat >&2 <<'EOF'
Firebase Auth authorized-domains preflight: could not acquire Google access token.
Checked:
  - Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS / ADC)
  - Firebase CLI local login token cache (~/.config/configstore/firebase-tools.json)
EOF
    if is_truthy_value "$require_authorized_domains"; then
      echo "Failing deploy because FIREBASE_REQUIRE_AUTHORIZED_DOMAINS=1." >&2
      exit 1
    fi
    echo "Warning: continuing local deploy without automated authorized-domain verification." >&2
    return 0
  fi

  local config_file
  config_file="$(mktemp)"
  if ! get_identity_platform_config "$token" "$config_file"; then
    rm -f "$config_file"
    echo "Failed to fetch Firebase Auth config from Identity Toolkit API for authorized-domain check." >&2
    if is_truthy_value "$require_authorized_domains"; then
      echo "Failing deploy because FIREBASE_REQUIRE_AUTHORIZED_DOMAINS=1." >&2
      exit 1
    fi
    echo "Warning: continuing local deploy without automated authorized-domain verification." >&2
    return 0
  fi

  local project_for_domains default_firebaseapp default_webapp
  local current_domains expected_required_domains expected_optional_domains
  local missing_required_domains missing_optional_domains
  local explicit_domains hosting_domains domain

  project_for_domains="${VITE_FIREBASE_PROJECT_ID:-${PROJECT_ID}}"
  default_firebaseapp="${project_for_domains}.firebaseapp.com"
  default_webapp="${project_for_domains}.web.app"
  current_domains="$(extract_authorized_domains "$config_file" || true)"
  expected_required_domains=""
  expected_optional_domains=""
  missing_required_domains=""
  missing_optional_domains=""

  # Optional: defaults are usually implicitly allowed; do not hard-fail if absent from API response.
  domain_list_add expected_optional_domains "$default_firebaseapp"
  domain_list_add expected_optional_domains "$default_webapp"
  domain_list_add expected_optional_domains "${VITE_FIREBASE_AUTH_DOMAIN:-}"

  explicit_domains="$(collect_authorized_domains_config || true)"
  if [ -n "$explicit_domains" ]; then
    while IFS= read -r domain; do
      [ -z "$domain" ] && continue
      domain_list_add expected_required_domains "$domain"
    done < <(printf '%s\n' "$explicit_domains")
  fi

  hosting_domains="$(discover_hosting_domains "$token" "${VITE_FIREBASE_PROJECT_ID:-${PROJECT_ID}}" || true)"
  if [ -n "$hosting_domains" ]; then
    while IFS= read -r domain; do
      [ -z "$domain" ] && continue
      if [ "$domain" = "$default_firebaseapp" ] || [ "$domain" = "$default_webapp" ]; then
        domain_list_add expected_optional_domains "$domain"
      else
        domain_list_add expected_required_domains "$domain"
      fi
    done <<< "$hosting_domains"
  fi

  while IFS= read -r domain; do
    [ -z "$domain" ] && continue
    if ! domain_list_contains "$current_domains" "$domain"; then
      domain_list_add missing_required_domains "$domain"
    fi
  done <<< "$expected_required_domains"

  while IFS= read -r domain; do
    [ -z "$domain" ] && continue
    if ! domain_list_contains "$current_domains" "$domain"; then
      domain_list_add missing_optional_domains "$domain"
    fi
  done <<< "$expected_optional_domains"

  rm -f "$config_file"

  if [ -n "$missing_required_domains" ]; then
    echo "Firebase Auth authorized-domains preflight found missing required domains:" >&2
    printf '%s\n' "$missing_required_domains" | sed 's/^/  - /' >&2
    cat >&2 <<'EOF'
Fix options:
  1) Configure Firebase Auth authorized domains in Console, then rerun deploy.
  2) To bypass locally (not recommended), set FIREBASE_REQUIRE_AUTHORIZED_DOMAINS=0.
EOF
    cat >&2 <<EOF
Manual Console steps:
  - Open: https://console.firebase.google.com/project/${PROJECT_ID}/authentication/settings
  - Under "Authorized domains", click "Add domain"
  - Add each missing required domain listed above (hostnames only; no https:// and no path)
  - Wait ~1-2 minutes for propagation, then rerun deploy
  - Optional: keep FIREBASE_AUTHORIZED_DOMAINS in .env to document expected domains for this project
EOF
    if is_truthy_value "$require_authorized_domains"; then
      echo "Failing deploy because FIREBASE_REQUIRE_AUTHORIZED_DOMAINS=1." >&2
      exit 1
    fi
    echo "Warning: continuing deploy (FIREBASE_REQUIRE_AUTHORIZED_DOMAINS=0)." >&2
  fi

  if [ -n "$missing_optional_domains" ]; then
    echo "Firebase Auth authorized-domains preflight warning: some optional/default domains are not listed by API:" >&2
    printf '%s\n' "$missing_optional_domains" | sed 's/^/  - /' >&2
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

sanitize_functions_source_for_deploy() {
  local removed_any=0
  local path=""

  while IFS= read -r path; do
    [ -z "$path" ] && continue
    rm -f "$path"
    removed_any=1
  done < <(find functions -type s -print 2>/dev/null || true)

  while IFS= read -r path; do
    [ -z "$path" ] && continue
    rm -f "$path"
    removed_any=1
  done < <(find functions -type p -print 2>/dev/null || true)

  while IFS= read -r path; do
    [ -z "$path" ] && continue
    rm -f "$path"
    removed_any=1
  done < <(find functions -path 'functions/venv' -prune -o -type l -print 2>/dev/null || true)

  if [ "$removed_any" -eq 1 ]; then
    echo "Sanitized functions source tree (removed sockets/fifos/symlinks) before Firebase upload."
  fi
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
preflight_frontend_firebase_config
print_firebase_auth_setup_overview
preflight_firebase_auth_signin_config
preflight_firebase_auth_authorized_domains

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

echo "Staging shared runtime modules into functions deploy source..."
stage_functions_src

echo "Preparing functions virtual environment with ${PYTHON_BIN}..."
rm -rf functions/venv
"$PYTHON_BIN" -m venv --copies functions/venv
functions/venv/bin/python -m pip install --upgrade pip
functions/venv/bin/python -m pip install -r functions/requirements.txt

sanitize_functions_source_for_deploy

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
