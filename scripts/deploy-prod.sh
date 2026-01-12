#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERRAFORM_DIR="${ROOT_DIR}/infra/terraform"
TF_VARS_FILE="${TF_VARS_FILE:-${TERRAFORM_DIR}/envs/prod/terraform.tfvars}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd aws
require_cmd terraform
require_cmd npm
require_cmd python

if [[ ! -f "$TF_VARS_FILE" ]]; then
  echo "tfvars file not found: $TF_VARS_FILE" >&2
  exit 1
fi

echo "Building Lambda package..."
"${ROOT_DIR}/scripts/build-lambda.sh"

echo "Applying Terraform..."
mkdir -p "$ROOT_DIR/dist"
pushd "$TERRAFORM_DIR" >/dev/null
if [[ -n "${TF_BACKEND_CONFIG_FILE:-}" ]]; then
  terraform init -backend-config="$TF_BACKEND_CONFIG_FILE"
else
  terraform init
fi
if [[ "${SKYBRIDGE_AUTO_APPROVE:-}" == "1" ]]; then
  terraform apply -var-file="$TF_VARS_FILE" -auto-approve
else
  terraform apply -var-file="$TF_VARS_FILE"
fi

echo "Reading Terraform outputs..."
terraform output -json > "$ROOT_DIR/dist/terraform-output.json"
popd >/dev/null

echo "Building frontend..."
ROOT_DIR_ENV="$ROOT_DIR" python - <<'PY'
import json
from pathlib import Path
import subprocess
import os

root = Path(os.environ["ROOT_DIR_ENV"]).resolve()
outputs_path = root / "dist" / "terraform-output.json"
payload = json.loads(outputs_path.read_text())

def val(name, default=""):
    entry = payload.get(name) or {}
    return entry.get("value") or default

api_base = val("api_base_url")
issuer = val("auth_issuer_url")
client_id = val("user_pool_client_id")
domain_prefix = val("user_pool_domain")
bucket = val("frontend_bucket_name")
distribution_id = val("cloudfront_distribution_id")
region = os.environ.get("AWS_REGION", "eu-west-1")

if not all([api_base, issuer, client_id, bucket, distribution_id]):
    missing = [k for k in ["api_base_url","auth_issuer_url","user_pool_client_id","frontend_bucket_name","cloudfront_distribution_id"] if not val(k)]
    raise SystemExit(f"Missing required terraform outputs: {', '.join(missing)}")

logout_url = ""
if domain_prefix:
    logout_url = f"https://{domain_prefix}.auth.{region}.amazoncognito.com/logout"

env = os.environ.copy()
env.update({
    "VITE_API_BASE_URL": api_base,
    "VITE_AUTH_MODE": "oidc",
    "VITE_AUTH_ISSUER_URL": issuer,
    "VITE_AUTH_CLIENT_ID": client_id,
    "VITE_AUTH_PROVIDER_PARAM": "identity_provider",
    "VITE_AUTH_REDIRECT_PATH": "/app/auth/callback",
})
if logout_url:
    env["VITE_AUTH_LOGOUT_URL"] = logout_url

subprocess.check_call(
    ["npm", "--prefix", str(root / "src" / "frontend"), "run", "build"],
    env=env,
)
PY
BUCKET_NAME="$(ROOT_DIR_ENV="$ROOT_DIR" python - <<'PY'
import json
from pathlib import Path
import os
root = Path(os.environ["ROOT_DIR_ENV"]).resolve()
payload = json.loads((root / "dist" / "terraform-output.json").read_text())
print(payload["frontend_bucket_name"]["value"])
PY
)"
DIST_ID="$(ROOT_DIR_ENV="$ROOT_DIR" python - <<'PY'
import json
from pathlib import Path
import os
root = Path(os.environ["ROOT_DIR_ENV"]).resolve()
payload = json.loads((root / "dist" / "terraform-output.json").read_text())
print(payload["cloudfront_distribution_id"]["value"])
PY
)"

echo "Syncing frontend to S3 bucket ${BUCKET_NAME}..."
aws s3 sync "${ROOT_DIR}/src/frontend/dist" "s3://${BUCKET_NAME}" --delete

if [[ "${SKIP_INVALIDATION:-}" != "1" ]]; then
  echo "Invalidating CloudFront distribution ${DIST_ID}..."
  aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*"
fi

echo "Deployment complete."
