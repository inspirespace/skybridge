#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
FIREBASERC_FILE="${FIREBASERC_FILE:-$ROOT_DIR/.firebaserc}"

json_get() {
  path_expr="$1"
  node - "$FIREBASERC_FILE" "$path_expr" <<'NODE'
const fs = require("fs");

const filePath = process.argv[2];
const pathExpr = process.argv[3];

if (!fs.existsSync(filePath)) {
  process.exit(0);
}

let data;
try {
  data = JSON.parse(fs.readFileSync(filePath, "utf8"));
} catch {
  process.exit(0);
}

let current = data;
for (const part of pathExpr.split(".")) {
  if (!part) {
    continue;
  }
  if (!current || typeof current !== "object" || !(part in current)) {
    process.exit(0);
  }
  current = current[part];
}

if (typeof current === "string" || typeof current === "number" || typeof current === "boolean") {
  process.stdout.write(String(current));
}
NODE
}

get_project() {
  if [ -n "${FIREBASE_PROJECT_ID:-}" ]; then
    printf '%s' "${FIREBASE_PROJECT_ID}"
    return 0
  fi
  json_get "projects.default"
}

get_region() {
  if [ -n "${FIREBASE_REGION:-}" ]; then
    printf '%s' "${FIREBASE_REGION}"
    return 0
  fi
  region="$(json_get "config.region")"
  if [ -n "${region}" ]; then
    printf '%s' "${region}"
  else
    printf 'europe-west1'
  fi
}

usage() {
  cat <<'EOF'
Usage: scripts/firebase-config.sh <project|region|exports>

Reads canonical Firebase config from .firebaserc.
EOF
}

case "${1:-}" in
  project)
    get_project
    ;;
  region)
    get_region
    ;;
  exports)
    project="$(get_project)"
    region="$(get_region)"
    if [ -n "${project}" ]; then
      printf 'FIREBASE_PROJECT_ID=%s\n' "${project}"
    fi
    printf 'FIREBASE_REGION=%s\n' "${region}"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
